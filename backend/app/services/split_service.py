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
from app.schemas.splitting import SplitManifest, SplitResult
from app.services.split_pipeline import (
    GROUP_COLUMN,
    RANDOM_STATE,
    SPLIT_VERSION,
    TARGET_COLUMN,
    TARGET_TEST_RATIO,
    select_group_stratified_holdout,
    validate_selection,
)
from app.storage.file_manager import read_json, write_json_atomic
from app.storage.job_manager import JobManager
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.utils.tabular import object_hash


class SplitService:
    def __init__(self, settings: Settings) -> None:
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)
        self._lock = CONFIGURATION_LOCK

    def create_split(self, job_id: str, test_ratio: float = TARGET_TEST_RATIO) -> SplitResult:
        with self._lock:
            config = self.configuration.get(job_id)
            manifest_path = self._manifest_path(job_id)
            if manifest_path.is_file():
                manifest = read_json(manifest_path)
                self.configuration.verify_snapshot(job_id, manifest['configuration'])
                return self._result_from_manifest(manifest)

            metadata = self.jobs.read_metadata(job_id)
            current_status = parse_job_status(metadata.get("status"))
            if current_status != JobStatus.PREPROCESSED:
                raise InvalidJobStateError(
                    "Split hanya dapat dibuat saat status job PREPROCESSED."
                )
            source_path = self.jobs.preprocessed_dataset_path(job_id)
            if not source_path.is_file():
                raise ArtifactNotFoundError("dataset_preprocessed.xlsx")
            dataframe = self._read_preprocessed(source_path)
            pre_report = read_json(self.jobs.report_path(job_id, 'preprocessing_report.json'))
            if not config.get('legacy') and pre_report['artifact_integrity'].get('dataset_configuration_sha256') != object_hash(config):
                raise InvalidDatasetError('Checksum konfigurasi preprocessing berubah.')
            try:
                selection = select_group_stratified_holdout(dataframe, test_ratio)
                validation = validate_selection(dataframe, selection)
            except ValueError as error:
                raise InvalidDatasetError(str(error)) from error
            if not validation["passed"]:
                raise InvalidDatasetError("Validasi isolasi split gagal.")

            train = dataframe.iloc[selection.train_indices]
            test = dataframe.iloc[selection.test_indices]
            created_at = self._now()
            train_distribution = self._distribution(train)
            test_distribution = self._distribution(test)
            manifest: dict[str, Any] = {
                "job_id": job_id,
                "created_at": created_at,
                "split_version": SPLIT_VERSION,
                "source_artifact": {
                    "path": "preprocessed/dataset_preprocessed.xlsx",
                    "sha256": self._sha256(source_path),
                    "preprocessing_version": str(
                        metadata.get("preprocessing_version", "unknown")
                    ),
                },
                "configuration": {
                    "requested_train_ratio": 1 - test_ratio,
                    "requested_test_ratio": test_ratio,
                    "random_state": RANDOM_STATE,
                    "stratified": True,
                    "group_aware": True,
                    "target_column": TARGET_COLUMN,
                    "group_column": GROUP_COLUMN,
                    "sampling": "NONE",
                },
                "selection": {
                    "strategy": selection.strategy,
                    "selected_candidate": selection.selected_candidate,
                    "actual_train_ratio": round(len(train) / len(dataframe), 8),
                    "actual_test_ratio": round(len(test) / len(dataframe), 8),
                },
                "train": {
                    "row_count": len(train),
                    "record_ids": train["record_id"].astype(str).tolist(),
                    "group_ids": sorted(train[GROUP_COLUMN].astype(str).unique().tolist()),
                    "class_distribution": train_distribution,
                },
                "test": {
                    "row_count": len(test),
                    "record_ids": test["record_id"].astype(str).tolist(),
                    "group_ids": sorted(test[GROUP_COLUMN].astype(str).unique().tolist()),
                    "class_distribution": test_distribution,
                },
                "validation": validation,
                "class_imbalance": {
                    "overall_distribution": self._distribution(dataframe),
                    "train_distribution": train_distribution,
                    "test_distribution": test_distribution,
                    "minority_class": min(self._distribution(dataframe), key=self._distribution(dataframe).get),
                    "sampling_applied": False,
                    "training_recommendation": "RandomForestClassifier(class_weight='balanced')",
                },
                "candidate_summaries": selection.candidate_summaries,
            }
            if not config.get('legacy'):
                manifest['configuration']['dataset_configuration'] = config
                manifest['configuration']['dataset_configuration_sha256'] = object_hash(config)
            write_json_atomic(manifest_path, manifest)
            self.jobs.update_metadata(
                job_id,
                {
                    "split_version": SPLIT_VERSION,
                    "split_created_at": created_at,
                    "split_train_rows": len(train),
                    "split_test_rows": len(test),
                    "split_random_state": RANDOM_STATE,
                    "split_manifest_sha256": self._sha256(manifest_path),
                },
            )
            return self._result_from_manifest(manifest)

    def manifest(self, job_id: str) -> SplitManifest:
        path = self._manifest_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("split_manifest.json")
        manifest = read_json(path)
        self.configuration.verify_snapshot(job_id, manifest['configuration'])
        return SplitManifest.model_validate(manifest)

    def manifest_path(self, job_id: str) -> Path:
        path = self._manifest_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("split_manifest.json")
        self.manifest(job_id)
        return path

    @staticmethod
    def _read_preprocessed(path: Path) -> pd.DataFrame:
        try:
            dataframe = pd.read_excel(
                path, sheet_name="DATA_PREPROCESSED", dtype=object, keep_default_na=False
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise InvalidDatasetError("Dataset preprocessed tidak dapat dibaca.") from error
        required = {"record_id", TARGET_COLUMN, GROUP_COLUMN}
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise InvalidDatasetError(
                "Dataset preprocessed tidak memenuhi kontrak split; kolom hilang: "
                + ", ".join(missing)
                + "."
            )
        return dataframe

    def _manifest_path(self, job_id: str) -> Path:
        return self.jobs.report_path(job_id, "split_manifest.json")

    @staticmethod
    def _distribution(dataframe: pd.DataFrame) -> dict[str, int]:
        return {
            str(label): int(count)
            for label, count in dataframe[TARGET_COLUMN].value_counts().items()
        }

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
    def _result_from_manifest(manifest: dict[str, Any]) -> SplitResult:
        return SplitResult(
            job_id=manifest["job_id"],
            status=JobStatus.PREPROCESSED.value,
            strategy=manifest["selection"]["strategy"],
            random_state=manifest["configuration"]["random_state"],
            train_rows=manifest["train"]["row_count"],
            test_rows=manifest["test"]["row_count"],
            actual_test_ratio=manifest["selection"]["actual_test_ratio"],
            train_distribution=manifest["train"]["class_distribution"],
            test_distribution=manifest["test"]["class_distribution"],
            group_overlap_count=manifest["validation"]["group_overlap_count"],
            record_overlap_count=manifest["validation"]["record_overlap_count"],
            split_version=manifest["split_version"],
            created_at=datetime.fromisoformat(manifest["created_at"]),
        )
