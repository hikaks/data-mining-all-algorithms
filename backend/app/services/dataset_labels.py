"""Import existing labels or identify raw rows once, with auditable provenance.

No model is trained here. Ambiguous rows remain excluded from training.
"""

from datetime import datetime, timezone
from hashlib import sha256
import math
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.core.dataset_contract import INPUT_LABEL_COLUMNS
from app.core.exceptions import InvalidDatasetError, InvalidJobStateError
from app.core.job_status import JOB_STATUS_ORDER, JobStatus, parse_job_status
from app.services.auto_labeling import AI_VALIDATOR_ROLE, POLICY_VERSION, classify_record
from app.services.cleaning.pipeline import _record_id
from app.services.cleaning.whitespace_cleaner import normalize_whitespace
from app.services.labeling_service import LabelingService
from app.storage.file_manager import read_json, write_excel_atomic, write_json_atomic
from app.storage.job_manager import JobManager
from app.utils.excel import inspect_workbook


def identify_raw_row(row: Any, timestamp: str) -> dict[str, Any]:
    decision = classify_record({
        "keluhan_solusi": normalize_whitespace(row["Keluhan_Solusi_Asli"]),
        "status": normalize_whitespace(row["Status_Asli"]),
    })
    return dict(zip(INPUT_LABEL_COLUMNS, (
        None if decision.label == "NEEDS_REVIEW" else decision.label,
        "NEEDS_REVIEW" if decision.label == "NEEDS_REVIEW" else "LABELED",
        AI_VALIDATOR_ROLE, timestamp, decision.confidence, decision.reason, POLICY_VERSION,
    )))


def validate_input_label(row: Any, source_row: int) -> dict[str, Any]:
    label = {name: None if pd.isna(row[name]) else row[name] for name in INPUT_LABEL_COLUMNS}
    for name in INPUT_LABEL_COLUMNS:
        if name != "label_confidence" and label[name] is not None:
            label[name] = str(label[name]).strip() or None
    status, target = label["labeling_status"], label["keputusan_laporan"]
    valid = (status == "LABELED" and target in {"SELESAI", "TINDAK_LANJUT"}) or (
        status == "NEEDS_REVIEW" and target is None
    )
    if not valid:
        raise InvalidDatasetError(f"Label baris Excel {source_row} tidak valid; target final atau NEEDS_REVIEW dengan target kosong diperlukan.")
    if label["label_validator_role"] not in {"AI_VALIDATOR", "ADMIN_VALIDATOR"}:
        raise InvalidDatasetError(f"Role label baris Excel {source_row} tidak valid.")
    if not label["label_decision_reason"] or not label["label_policy_version"]:
        raise InvalidDatasetError(f"Alasan dan versi kebijakan label baris Excel {source_row} wajib tersedia.")
    try:
        datetime.fromisoformat(label["label_updated_at"] or "")
        confidence = label["label_confidence"]
        if confidence is not None:
            confidence = float(confidence)
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("confidence")
        elif label["label_validator_role"] == AI_VALIDATOR_ROLE:
            raise ValueError("confidence")
        label["label_confidence"] = confidence
    except (TypeError, ValueError) as error:
        raise InvalidDatasetError(f"Tanggal audit atau confidence label baris Excel {source_row} tidak valid.") from error
    return label


def build_input_labels(dataframe: pd.DataFrame, job_id: str, raw_sha256: str) -> dict[str, Any]:
    imported = "keputusan_laporan" in dataframe.columns
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    counts = {"SELESAI": 0, "TINDAK_LANJUT": 0, "NEEDS_REVIEW": 0}
    for index, row in dataframe.iterrows():
        source_row = int(index) + 2
        label = validate_input_label(row, source_row) if imported else identify_raw_row(row, now)
        counts[label["keputusan_laporan"] or "NEEDS_REVIEW"] += 1
        rows.append({"source_row": source_row, "record_id": _record_id(job_id, source_row), **label})
    return {
        "job_id": job_id, "created_at": now, "source": "IMPORTED" if imported else "AUTO_IDENTIFIED",
        "raw_sha256": raw_sha256, "total_records": len(rows), "decision_counts": counts,
        "policy_version": POLICY_VERSION if not imported else "WORKBOOK_LABELS",
        "warning": "Label adalah evidence yang disediakan/diidentifikasi, bukan ground-truth manusia independen yang diverifikasi aplikasi.",
        "rows": rows,
    }


class DatasetLabelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs = JobManager(settings.storage_root)

    def ensure_input(self, job_id: str) -> dict[str, Any]:
        raw = self.jobs.raw_dataset_path(job_id)
        raw_hash = sha256(raw.read_bytes()).hexdigest()
        path = self.jobs.report_path(job_id, "input_labels.json")
        if path.is_file():
            snapshot = read_json(path)
            if snapshot["raw_sha256"] != raw_hash:
                raise InvalidDatasetError("Checksum workbook sumber label tidak cocok.")
            return snapshot
        dataframe = inspect_workbook(raw, self.settings.required_sheet, self.settings.required_columns)
        snapshot = build_input_labels(dataframe, job_id, raw_hash)
        write_json_atomic(path, snapshot)
        self.jobs.update_metadata(job_id, {"input_label_source": snapshot["source"], "input_label_counts": snapshot["decision_counts"]})
        return snapshot

    def attach_cleaned(self, job_id: str, dataframe: pd.DataFrame, cleaning_report: dict[str, Any]) -> pd.DataFrame:
        snapshot = self.ensure_input(job_id)
        by_id = {row["record_id"]: row for row in snapshot["rows"]}
        for duplicate in cleaning_report["duplicate_records"]:
            removed, kept = by_id[duplicate["record_id"]], by_id[duplicate["kept_record_id"]]
            if (removed["keputusan_laporan"], removed["labeling_status"]) != (kept["keputusan_laporan"], kept["labeling_status"]):
                raise InvalidDatasetError("Exact duplicate memiliki label bertentangan. Perbaiki label workbook sebelum cleaning; label tidak dibuang diam-diam.")
        for name in INPUT_LABEL_COLUMNS:
            dataframe[name] = [by_id[str(record_id)][name] for record_id in dataframe["record_id"]]
        return dataframe

    def persist_cleaned_labels(self, job_id: str, dataframe: pd.DataFrame) -> None:
        snapshot = self.ensure_input(job_id)
        service = LabelingService(self.settings)
        report = {
            "job_id": job_id, "created_at": snapshot["created_at"], "updated_at": snapshot["created_at"],
            "validator_role": "WORKBOOK_IMPORT" if snapshot["source"] == "IMPORTED" else AI_VALIDATOR_ROLE,
            "source_evidence_policy": snapshot["warning"], "input_label_source": snapshot["source"],
            "input_raw_sha256": snapshot["raw_sha256"],
            "events": [{
                "event_type": "label_recorded", "operation": "IMPORT_LABEL" if snapshot["source"] == "IMPORTED" else "UPLOAD_AUTO_IDENTIFY",
                "record_id": str(row["record_id"]), "new_target": row["keputusan_laporan"],
                "new_labeling_status": row["labeling_status"], "validator_role": row["label_validator_role"],
                "reason": row["label_decision_reason"], "confidence": row["label_confidence"],
                "policy_version": row["label_policy_version"], "created_at": row["label_updated_at"],
            } for row in dataframe.to_dict(orient="records")],
        }
        service._persist(job_id, dataframe, report)
        self.jobs.update_metadata(job_id, {"status": JobStatus.LABELED.value})

    def ensure_for_preprocessing(self, job_id: str) -> None:
        """Upgrade unfinished legacy jobs only; never touch a trained job's labels."""
        metadata = self.jobs.read_metadata(job_id)
        status = parse_job_status(metadata.get("status"))
        if JOB_STATUS_ORDER[status] < JOB_STATUS_ORDER[JobStatus.CLEANED]:
            raise InvalidJobStateError("Jalankan cleaning sebelum preprocessing.")
        if JOB_STATUS_ORDER[status] >= JOB_STATUS_ORDER[JobStatus.PREPROCESSED]:
            return
        path = self.jobs.labeled_dataset_path(job_id)
        report_path = self.jobs.report_path(job_id, "labeling_report.json")
        if path.is_file() != report_path.is_file():
            raise InvalidDatasetError("Artifact label tidak lengkap; dataset dan report harus tersedia bersama.")
        if path.is_file():
            dataframe = LabelingService(self.settings)._read_labeled(path)
            pending = dataframe["labeling_status"].fillna("UNLABELED").eq("UNLABELED")
            if pending.any():
                # Preserve all existing final/review decisions and historical audit events.
                from app.schemas.labeling import AutoLabelRequest
                LabelingService(self.settings).auto_label(job_id, AutoLabelRequest(overwrite_existing=False))
            return
        cleaned = pd.read_excel(self.jobs.cleaned_dataset_path(job_id), sheet_name="DATA_CLEANED", dtype=object)
        report = read_json(self.jobs.report_path(job_id, "cleaning_report.json"))
        self.attach_cleaned(job_id, cleaned, report)
        self.persist_cleaned_labels(job_id, cleaned)
