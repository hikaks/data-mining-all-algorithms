from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.core.exceptions import (
    ArtifactNotFoundError,
    InvalidDatasetError,
    InvalidJobStateError,
)
from app.core.job_status import JOB_STATUS_ORDER, JobStatus, parse_job_status
from app.schemas.preprocessing import PreprocessingReport, PreprocessingResult
from app.services.preprocessing_pipeline import (
    CATEGORICAL_FEATURES,
    IDENTIFIER_COLUMNS,
    MODEL_FEATURES,
    NEAR_DUPLICATE_THRESHOLD,
    NUMERIC_FEATURES,
    PREPROCESSING_VERSION,
    TARGET_COLUMN,
    TEXT_FEATURES,
    assert_feature_contract,
    class_ratio,
    detect_near_duplicates,
    finite_numeric_features,
    normalize_report_text,
    technician_count,
    transformer_spec,
)
from app.services.dataset_labels import DatasetLabelService
from app.storage.file_manager import read_json, write_excel_atomic, write_json_atomic
from app.storage.job_manager import JobManager
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.utils.tabular import object_hash


FINAL_LABELS = ("SELESAI", "TINDAK_LANJUT")
OUTPUT_COLUMNS = (
    *IDENTIFIER_COLUMNS,
    *MODEL_FEATURES,
    TARGET_COLUMN,
)


class PreprocessingService:
    def __init__(self, settings: Settings) -> None:
        self.labels = DatasetLabelService(settings)
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)
        self.settings = settings
        self._lock = CONFIGURATION_LOCK

    def preprocess(self, job_id: str) -> PreprocessingResult:
        with self._lock:
            config = self.configuration.get(job_id)
            if config['profile'] == 'generic':
                from app.services.generic_workflow import GenericWorkflowService
                return GenericWorkflowService(self.settings).preprocess(job_id)
            self.labels.ensure_for_preprocessing(job_id)
            metadata = self.jobs.read_metadata(job_id)
            current_status = parse_job_status(metadata.get("status"))
            if JOB_STATUS_ORDER[current_status] < JOB_STATUS_ORDER[JobStatus.LABELING]:
                raise InvalidJobStateError(
                    "Preprocessing hanya dapat dimulai setelah historical labeling."
                )
            if JOB_STATUS_ORDER[current_status] > JOB_STATUS_ORDER[JobStatus.PREPROCESSED]:
                raise InvalidJobStateError(
                    f"Preprocessing dikunci karena job sudah {current_status.value}."
                )

            report_path = self._report_path(job_id)
            output_path = self.jobs.preprocessed_dataset_path(job_id)
            if output_path.is_file() or report_path.is_file():
                if not output_path.is_file() or not report_path.is_file():
                    raise InvalidDatasetError(
                        "Artifact preprocessing tidak lengkap; dataset dan report harus tersedia bersama."
                    )
                return self._result_from_report(read_json(report_path))

            if not metadata.get("training_ready"):
                raise InvalidJobStateError(
                    "Training gate labeling belum siap untuk preprocessing."
                )
            labeled_path = self.jobs.labeled_dataset_path(job_id)
            if not labeled_path.is_file():
                raise ArtifactNotFoundError("dataset_labeled.xlsx")
            dataframe = self._read_labeled(labeled_path)
            prepared, excluded = self._prepare_rows(dataframe)
            if prepared.empty:
                raise InvalidDatasetError(
                    "Tidak ada record yang memenuhi kontrak preprocessing."
                )

            target_counts = {
                key: int(value)
                for key, value in prepared[TARGET_COLUMN].value_counts().items()
            }
            if any(target_counts.get(label, 0) < 2 for label in FINAL_LABELS):
                raise InvalidDatasetError(
                    "Setiap kelas membutuhkan minimal dua record setelah exclusion preprocessing."
                )

            duplicate_result = detect_near_duplicates(prepared)
            prepared["near_duplicate_group_id"] = duplicate_result.group_ids
            prepared = prepared.loc[:, list(OUTPUT_COLUMNS)]
            assert_feature_contract(list(MODEL_FEATURES))
            if not finite_numeric_features(prepared):
                raise InvalidDatasetError(
                    "Fitur numerik preprocessing mengandung NaN atau infinite value."
                )

            completed_at = self._now()
            write_excel_atomic(output_path, prepared, "DATA_PREPROCESSED")
            excluded_counts: dict[str, int] = {}
            for item in excluded:
                reason = item["reason"]
                excluded_counts[reason] = excluded_counts.get(reason, 0) + 1
            report: dict[str, Any] = {
                "job_id": job_id,
                "generated_at": completed_at,
                "preprocessing_version": PREPROCESSING_VERSION,
                "source_rows": len(dataframe),
                "output_rows": len(prepared),
                "excluded_rows": len(excluded),
                "excluded_counts": excluded_counts,
                "excluded_records": excluded,
                "target_distribution": target_counts,
                "class_imbalance_ratio": class_ratio(target_counts),
                "feature_contract": {
                    "identifier_columns": list(IDENTIFIER_COLUMNS),
                    "model_feature_columns": list(MODEL_FEATURES),
                    "target_column": TARGET_COLUMN,
                    "text_features": list(TEXT_FEATURES),
                    "categorical_features": list(CATEGORICAL_FEATURES),
                    "numeric_features": list(NUMERIC_FEATURES),
                },
                "leakage_audit": {
                    "passed": True,
                    "target_excluded_from_features": True,
                    "status_source_excluded_from_features": True,
                    "source_metadata_excluded_from_features": True,
                    "personal_name_fields_excluded_from_features": True,
                    "near_duplicate_group_excluded_from_features": True,
                    "weak_supervision_warning": (
                        "Target diturunkan dari status sumber dan teks oleh ai-assisted-id-v1; "
                        "evaluasi mengukur konsistensi terhadap kebijakan, bukan ground-truth "
                        "manusia independen."
                    ),
                },
                "transformer_spec": transformer_spec(),
                "near_duplicate_evaluation": {
                    "method": "char_wb_tfidf_cosine_same_customer",
                    "threshold": NEAR_DUPLICATE_THRESHOLD,
                    "automatic_removal": False,
                    "pair_count": duplicate_result.pair_count,
                    "group_count": len(duplicate_result.groups),
                    "groups": duplicate_result.groups,
                    "sample_pairs": duplicate_result.sample_pairs,
                    "sample_pairs_truncated": duplicate_result.pair_count
                    > len(duplicate_result.sample_pairs),
                    "conflicting_label_groups": duplicate_result.conflicting_label_groups,
                },
                "artifact_integrity": {
                    "input_labeled_sha256": self._sha256(labeled_path),
                    "output_preprocessed_sha256": self._sha256(output_path),
                },
            }
            if not config.get('legacy'):
                report['artifact_integrity']['dataset_configuration_sha256'] = object_hash(config)
            write_json_atomic(report_path, report)
            self.jobs.update_metadata(
                job_id,
                {
                    "status": JobStatus.PREPROCESSED.value,
                    "preprocessed_rows": len(prepared),
                    "preprocessing_excluded_rows": len(excluded),
                    "preprocessing_version": PREPROCESSING_VERSION,
                    "preprocessing_completed_at": completed_at,
                    "near_duplicate_groups": len(duplicate_result.groups),
                },
            )
            return self._result_from_report(report)

    def report(self, job_id: str) -> PreprocessingReport:
        self.configuration.get(job_id)
        path = self._report_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("preprocessing_report.json")
        return PreprocessingReport.model_validate(read_json(path))

    def preprocessed_path(self, job_id: str) -> Path:
        self.configuration.get(job_id)
        path = self.jobs.preprocessed_dataset_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("dataset_preprocessed.xlsx")
        return path

    def _prepare_rows(
        self, dataframe: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[dict[str, str]]]:
        final_mask = dataframe[TARGET_COLUMN].isin(FINAL_LABELS)
        valid_date_mask = dataframe["tanggal_valid"].map(self._truthy)
        text_mask = dataframe["keluhan_solusi"].map(normalize_report_text).ne("")
        parsed_dates = pd.to_datetime(dataframe["tanggal"], errors="coerce")
        parsed_date_mask = parsed_dates.notna()
        include_mask = final_mask & valid_date_mask & text_mask & parsed_date_mask

        excluded: list[dict[str, str]] = []
        for index, row in dataframe.loc[~include_mask].iterrows():
            if not final_mask.at[index]:
                reason = "LABEL_NOT_FINAL"
            elif not valid_date_mask.at[index] or not parsed_date_mask.at[index]:
                reason = "INVALID_DATE_OUTSIDE_RESEARCH_PERIOD"
            else:
                reason = "EMPTY_REPORT_TEXT"
            excluded.append({"record_id": str(row["record_id"]), "reason": reason})

        included = dataframe.loc[include_mask].copy()
        included_dates = parsed_dates.loc[include_mask]
        prepared = pd.DataFrame(
            {
                "record_id": included["record_id"].astype(str),
                "near_duplicate_group_id": "",
                "text_laporan": included["keluhan_solusi"].map(normalize_report_text),
                "customer": included["customer"].map(normalize_report_text).replace("", "UNKNOWN"),
                "teknisi": included["teknisi"].map(normalize_report_text).replace("", "UNKNOWN"),
                "tahun": included_dates.dt.year.astype(int),
                "bulan": included_dates.dt.month.astype(int),
                "hari_dalam_minggu": included_dates.dt.dayofweek.astype(int),
                "jumlah_teknisi": included["teknisi"].map(technician_count).astype(int),
                TARGET_COLUMN: included[TARGET_COLUMN].astype(str),
            }
        )
        return prepared.reset_index(drop=True), excluded

    @staticmethod
    def _read_labeled(path: Path) -> pd.DataFrame:
        try:
            dataframe = pd.read_excel(path, sheet_name="DATA_LABELED", dtype=object)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise InvalidDatasetError("Dataset labeled tidak dapat dibaca.") from error
        required = {
            "record_id",
            "tanggal",
            "tanggal_valid",
            "customer",
            "teknisi",
            "keluhan_solusi",
            TARGET_COLUMN,
        }
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise InvalidDatasetError(
                "Dataset labeled tidak memenuhi kontrak preprocessing; kolom hilang: "
                + ", ".join(missing)
                + "."
            )
        if dataframe["record_id"].duplicated().any():
            raise InvalidDatasetError("record_id pada dataset labeled harus unik.")
        return dataframe

    def _report_path(self, job_id: str) -> Path:
        return self.jobs.report_path(job_id, "preprocessing_report.json")

    @staticmethod
    def _truthy(value: Any) -> bool:
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes"}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _result_from_report(report: dict[str, Any]) -> PreprocessingResult:
        near_duplicates = report["near_duplicate_evaluation"]
        return PreprocessingResult(
            job_id=report["job_id"],
            status=JobStatus.PREPROCESSED.value,
            source_rows=report["source_rows"],
            output_rows=report["output_rows"],
            excluded_rows=report["excluded_rows"],
            target_distribution=report["target_distribution"],
            near_duplicate_groups=near_duplicates["group_count"],
            near_duplicate_pairs=near_duplicates["pair_count"],
            label_conflict_groups=len(near_duplicates["conflicting_label_groups"]),
            preprocessing_version=report["preprocessing_version"],
            completed_at=datetime.fromisoformat(report["generated_at"]),
        )
