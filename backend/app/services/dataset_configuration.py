"""Versioned per-job contracts; legacy defaults are read-only adapters."""
from collections import Counter
from datetime import datetime, timezone
from threading import RLock
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.core.dataset_contract import INPUT_LABEL_COLUMNS
from app.core.exceptions import InvalidDatasetError, InvalidJobStateError
from app.schemas.dataset import DatasetConfigurationRequest
from app.services.dataset_labels import build_input_labels
from app.services.data_understanding_service import build_summary, summary_to_json
from app.services.preprocessing_pipeline import MODEL_FEATURES
from app.storage.file_manager import read_json, write_json_atomic
from app.storage.job_manager import JobManager
from app.utils.excel import dataframe_records, inspect_workbook
from app.utils.tabular import content_hash, feature_value, label_value, missing, object_hash, read_input, suggested_kind


CONFIGURATION_LOCK = RLock()


def generic_summary(job_id: str, frame: pd.DataFrame, sheet: str | None, target: str | None = None) -> dict[str, Any]:
    columns = []
    for name in frame.columns:
        count = sum(missing(value) for value in frame[name])
        columns.append({"name": name, "dtype": suggested_kind(frame[name]), "missing_count": count,
                        "missing_percentage": round(count / len(frame) * 100, 2),
                        "non_missing_count": len(frame) - count, "unique_count": frame[name].nunique()})
    distributions = {}
    if target:
        counts = Counter(label_value(value) for value in frame[target])
        distributions["target"] = [{"value": key, "count": value} for key, value in counts.items() if key is not None]
    return {"job_id": job_id, "sheet_name": sheet or "CSV", "row_count": len(frame), "column_count": len(frame.columns),
            "duplicate_rows": int(frame.duplicated().sum()), "operationally_empty_rows": sum(all(missing(value) for value in row) for row in frame.itertuples(index=False, name=None)),
            "date_range": {}, "distributions": distributions, "columns": columns,
            "generated_at": datetime.now(timezone.utc).isoformat()}


class DatasetConfigurationService:
    def verify_snapshot(self, job_id, container):
        config = self.get(job_id)
        if config.get('legacy'):
            return
        expected = container.get('dataset_configuration_sha256')
        if expected != object_hash(config) or container.get('dataset_configuration') != config:
            raise InvalidDatasetError('Checksum snapshot konfigurasi dataset tidak valid.')

    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs = JobManager(settings.storage_root)

    def path(self, job_id: str):
        return self.jobs.require_job_path(job_id) / "config" / "dataset_config.json"

    def get(self, job_id: str) -> dict[str, Any]:
        with CONFIGURATION_LOCK:
            return self._get(job_id)

    def _get(self, job_id: str) -> dict[str, Any]:
        metadata = self.jobs.read_metadata(job_id)
        path = self.path(job_id)
        if path.is_file():
            config = read_json(path)
            if object_hash(config) != metadata.get("dataset_configuration_sha256"):
                raise InvalidDatasetError("Checksum konfigurasi dataset tidak valid.")
            if config["raw_sha256"] != content_hash(self.jobs.raw_dataset_path(job_id)):
                raise InvalidDatasetError("Checksum sumber dataset berubah.")
            return config
        if "configuration_ready" in metadata:
            raise InvalidJobStateError("Pilih target dan fitur, lalu simpan konfigurasi sebelum melanjutkan.")
        return {"schema_version": 1, "profile": "maxkomp", "legacy": True,
                "sheet_name": self.settings.required_sheet, "target_column": "keputusan_laporan",
                "features": self.preset_features(), "delimiter": None}

    @staticmethod
    def preset_features() -> list[dict[str, str]]:
        return [{"name": name, "kind": "text" if name == "text_laporan" else "categorical" if name in {"customer", "teknisi"} else "numeric"} for name in MODEL_FEATURES]

    def schema(self, job_id: str, sheet: str | None = None, delimiter: str | None = None, target: str | None = None) -> dict[str, Any]:
        metadata = self.jobs.read_metadata(job_id)
        selected = sheet or metadata.get("sheet_name")
        separator = delimiter or metadata.get("delimiter")
        frame = read_input(self.jobs.raw_dataset_path(job_id), selected, separator)
        allowed = list(self.settings.required_columns)
        preset = metadata.get("file_format", "xlsx") == "xlsx" and selected == self.settings.required_sheet and list(frame.columns) in [allowed, [*allowed, *INPUT_LABEL_COLUMNS]]
        summary = generic_summary(job_id, frame, selected, target if target in frame.columns else None)
        warnings = []
        for column in summary["columns"]:
            name = column["name"]
            if name.lower().endswith("id") or column["unique_count"] == len(frame) or name in INPUT_LABEL_COLUMNS or any(token in name.lower() for token in ('target', 'label', 'result', 'outcome', 'keputusan', 'status')):
                warnings.append(f"{name}: periksa identifier atau informasi hasil/audit sebelum menjadikannya fitur.")
            if target in frame.columns and name != target and all(label_value(a) == label_value(b) for a, b in zip(frame[name], frame[target])):
                warnings.append(f'{name}: nilai identik dengan target {target}; potensi kebocoran hasil.')
        return {"sheet_name": selected, "sheets": metadata.get("sheets", [self.settings.required_sheet]),
                "delimiter": separator, "delimiter_ambiguous": metadata.get("delimiter_ambiguous", False),
                "maxkomp_available": preset, "row_count": len(frame), "columns": summary["columns"],
                "preview": dataframe_records(frame.head(5)), "target_distribution": summary["distributions"].get("target", []),
                "target_missing": sum(missing(value) for value in frame[target]) if target in frame.columns else 0,
                "warnings": warnings, "locked": 'configuration_ready' not in metadata or metadata.get("status") not in {"UPLOADED", "ANALYZED"}}

    def save(self, job_id: str, payload: DatasetConfigurationRequest) -> dict[str, Any]:
        with CONFIGURATION_LOCK:
            metadata = self.jobs.read_metadata(job_id)
            if 'configuration_ready' not in metadata:
                raise InvalidJobStateError('Job lama memakai adapter preset read-only. Upload job baru untuk konfigurasi berbeda.')
            if metadata.get("status") not in {"UPLOADED", "ANALYZED"}:
                raise InvalidJobStateError("Konfigurasi terkunci setelah cleaning. Upload sebagai job baru untuk mengubahnya.")
            raw = self.jobs.raw_dataset_path(job_id)
            sheet = payload.sheet_name or metadata.get("sheet_name")
            delimiter = payload.delimiter or metadata.get("delimiter")
            frame = read_input(raw, sheet, delimiter)
            features = [feature.model_dump() for feature in payload.features]
            if payload.profile == "maxkomp":
                if raw.suffix != ".xlsx" or sheet != self.settings.required_sheet or payload.target_column != "keputusan_laporan":
                    raise InvalidDatasetError("Preset PT Maxkomp hanya untuk workbook/sheet resmi dan target keputusan_laporan.")
                frame = inspect_workbook(raw, sheet, self.settings.required_columns)
                if features and features != self.preset_features():
                    raise InvalidDatasetError("Preset mempertahankan tujuh fitur resmi. Gunakan profil Umum untuk memilih fitur lain.")
                features = self.preset_features()
                labels = build_input_labels(frame, job_id, content_hash(raw))
                summary = summary_to_json(build_summary(job_id, sheet, frame, self.settings.data_start_date, self.settings.data_cutoff_date))
            else:
                names = [feature["name"] for feature in features]
                if payload.target_column not in frame.columns or not names or len(set(names)) != len(names) or any(name not in frame.columns for name in names):
                    raise InvalidDatasetError("Pilih target yang tersedia dan minimal satu fitur unik dari dataset.")
                if payload.target_column in names:
                    raise InvalidDatasetError("Kolom target tidak boleh menjadi fitur model.")
                for feature in features:
                    values = frame[feature["name"]]
                    if all(missing(value) for value in values):
                        raise InvalidDatasetError(f"Fitur {feature['name']} seluruhnya kosong.")
                    for index, value in enumerate(values, 2):
                        feature_value(value, feature["kind"], f"Kolom {feature['name']}, baris {index}")
                counts = Counter(label_value(value) for value in frame[payload.target_column])
                counts.pop(None, None)
                if len(counts) < 2:
                    raise InvalidDatasetError("Target harus mempunyai minimal dua kelas berlabel. Regresi tidak didukung.")
                labels = {"source": "SOURCE_COLUMN", "raw_sha256": content_hash(raw), "decision_counts": dict(counts),
                          "target_column": payload.target_column, "missing_target": sum(missing(value) for value in frame[payload.target_column])}
                summary = generic_summary(job_id, frame, sheet, payload.target_column)
            previous = read_json(self.path(job_id)) if self.path(job_id).is_file() else {}
            config = {"schema_version": 1, 'revision': int(previous.get('revision', 0)) + 1, 'saved_at': datetime.now(timezone.utc).isoformat(), "profile": payload.profile, "sheet_name": sheet,
                      "delimiter": delimiter, "target_column": payload.target_column, "features": features,
                      "raw_sha256": content_hash(raw)}
            write_json_atomic(self.path(job_id), config)
            write_json_atomic(self.jobs.report_path(job_id, "input_labels.json"), labels)
            write_json_atomic(self.jobs.report_path(job_id, "data_understanding.json"), summary)
            self.jobs.update_metadata(job_id, {"configuration_ready": True, "dataset_configuration_sha256": object_hash(config),
                "profile": payload.profile, "sheet_name": sheet, "delimiter": delimiter, "target_column": payload.target_column,
                "status": "ANALYZED", "raw_rows": len(frame), "raw_columns": len(frame.columns),
                "input_label_source": labels["source"], "input_label_counts": labels["decision_counts"]})
            return config
