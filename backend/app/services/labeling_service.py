from datetime import datetime, timezone
import math
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.core.exceptions import (
    ArtifactNotFoundError,
    InvalidDatasetError,
    InvalidJobStateError,
    RecordNotFoundError,
)
from app.core.job_status import (
    JOB_STATUS_ORDER,
    JobStatus,
    parse_job_status,
    require_status_at_most,
)
from app.schemas.labeling import (
    AutoLabelingResult,
    AutoLabelRequest,
    BulkLabelRequest,
    LabelFilter,
    LabelUpdateRequest,
    LabelingMutationResult,
    LabelingPage,
    LabelingSummary,
)
from app.services.auto_labeling import (
    AI_VALIDATOR_ROLE,
    POLICY_VERSION,
    classify_record,
)
from app.storage.file_manager import read_json, write_excel_atomic, write_json_atomic
from app.storage.job_manager import JobManager
from app.utils.excel import dataframe_records


VALID_FINAL_LABELS = ("SELESAI", "TINDAK_LANJUT")
LABELING_STATUSES = ("UNLABELED", "LABELED", "NEEDS_REVIEW")
VALIDATOR_ROLE = "ADMIN_VALIDATOR"
LABEL_COLUMNS = (
    "labeling_status",
    "label_validator_role",
    "label_updated_at",
)
AI_AUDIT_COLUMNS = (
    "label_confidence",
    "label_decision_reason",
    "label_policy_version",
)


class LabelingService:
    def __init__(self, settings: Settings) -> None:
        self.jobs = JobManager(settings.storage_root)
        self._lock = Lock()

    def initialize(self, job_id: str) -> LabelingSummary:
        with self._lock:
            metadata = self.jobs.read_metadata(job_id)
            current_status = parse_job_status(metadata.get("status"))
            if JOB_STATUS_ORDER[current_status] < JOB_STATUS_ORDER[JobStatus.CLEANED]:
                raise InvalidJobStateError(
                    "Historical labeling hanya dapat dimulai setelah cleaning selesai."
                )
            require_status_at_most(current_status, JobStatus.LABELED, "labeling")

            labeled_path = self.jobs.labeled_dataset_path(job_id)
            report_path = self._report_path(job_id)
            if labeled_path.is_file() or report_path.is_file():
                if not labeled_path.is_file() or not report_path.is_file():
                    raise InvalidDatasetError(
                        "Artifact labeling tidak lengkap; dataset dan report harus tersedia bersama."
                    )
                dataframe = self._read_labeled(labeled_path)
                report = read_json(report_path)
                return self._persist(job_id, dataframe, report)

            cleaned_path = self.jobs.cleaned_dataset_path(job_id)
            if not cleaned_path.is_file():
                raise ArtifactNotFoundError("dataset_cleaned.xlsx")
            try:
                dataframe = pd.read_excel(
                    cleaned_path, sheet_name="DATA_CLEANED", dtype=object
                )
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise InvalidDatasetError(
                    "Dataset bersih tidak dapat dibaca untuk historical labeling."
                ) from error
            if dataframe.empty:
                raise InvalidDatasetError("Dataset bersih tidak memiliki record untuk dilabeli.")
            if "record_id" not in dataframe or "keputusan_laporan" not in dataframe:
                raise InvalidDatasetError(
                    "Dataset bersih tidak memiliki record_id atau keputusan_laporan."
                )
            if dataframe["record_id"].duplicated().any():
                raise InvalidDatasetError("record_id pada dataset bersih harus unik.")

            dataframe["labeling_status"] = dataframe["keputusan_laporan"].map(
                lambda value: "LABELED" if str(value) in VALID_FINAL_LABELS else "UNLABELED"
            )
            dataframe["label_validator_role"] = None
            dataframe["label_updated_at"] = None
            dataframe["label_confidence"] = None
            dataframe["label_decision_reason"] = None
            dataframe["label_policy_version"] = None
            now = self._now()
            report: dict[str, Any] = {
                "job_id": job_id,
                "created_at": now,
                "updated_at": now,
                "validator_role": VALIDATOR_ROLE,
                "label_definitions": {
                    "SELESAI": (
                        "Laporan dapat ditutup berdasarkan keputusan admin dan tidak "
                        "membutuhkan tindakan teknis atau administratif lanjutan."
                    ),
                    "TINDAK_LANJUT": (
                        "Laporan belum dapat ditutup karena masih terdapat tindakan "
                        "teknis dan/atau administratif."
                    ),
                    "NEEDS_REVIEW": (
                        "Keputusan belum dapat ditentukan dan record tidak boleh "
                        "digunakan untuk training."
                    ),
                },
                "source_evidence_policy": (
                    "Status sumber dan teks laporan digunakan sebagai bukti oleh kebijakan "
                    "AI-assisted yang transparan; keputusan dan confidence diaudit."
                ),
                "events": [],
            }
            return self._persist(job_id, dataframe, report)

    def summary(self, job_id: str) -> LabelingSummary:
        dataframe, report = self._load_state(job_id)
        return self._summary_from_state(job_id, dataframe, report)

    def records(
        self,
        job_id: str,
        label_filter: LabelFilter,
        page: int,
        page_size: int,
    ) -> LabelingPage:
        dataframe, _ = self._load_state(job_id)
        filtered = self._filter(dataframe, label_filter)
        total_items = len(filtered)
        start = (page - 1) * page_size
        page_frame = filtered.iloc[start : start + page_size]
        return LabelingPage(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=math.ceil(total_items / page_size) if total_items else 0,
            label_filter=label_filter,
            items=dataframe_records(page_frame),
        )

    def update_one(
        self, job_id: str, record_id: str, request: LabelUpdateRequest
    ) -> LabelingMutationResult:
        with self._lock:
            self._require_mutable(job_id)
            dataframe, report = self._load_state(job_id)
            matches = dataframe.index[dataframe["record_id"] == record_id].tolist()
            if not matches:
                raise RecordNotFoundError(record_id)
            changed = self._apply_label(
                dataframe,
                matches[0],
                request.label,
                request.reason,
                report,
                "SINGLE_LABEL",
            )
            summary = self._persist(job_id, dataframe, report)
            return LabelingMutationResult(
                updated_record_ids=[record_id] if changed else [],
                unchanged_record_ids=[] if changed else [record_id],
                summary=summary,
            )

    def update_bulk(
        self, job_id: str, request: BulkLabelRequest
    ) -> LabelingMutationResult:
        with self._lock:
            self._require_mutable(job_id)
            dataframe, report = self._load_state(job_id)
            record_ids = list(dict.fromkeys(request.record_ids))
            index_by_id = {
                str(record_id): index
                for index, record_id in dataframe["record_id"].items()
            }
            missing = [record_id for record_id in record_ids if record_id not in index_by_id]
            if missing:
                raise RecordNotFoundError(missing[0])

            self._validate_relabel_reason(
                dataframe,
                [index_by_id[record_id] for record_id in record_ids],
                request.label,
                request.reason,
            )
            updated: list[str] = []
            unchanged: list[str] = []
            for record_id in record_ids:
                changed = self._apply_label(
                    dataframe,
                    index_by_id[record_id],
                    request.label,
                    request.reason,
                    report,
                    "BULK_LABEL",
                    validate_reason=False,
                )
                (updated if changed else unchanged).append(record_id)
            summary = self._persist(job_id, dataframe, report)
            return LabelingMutationResult(
                updated_record_ids=updated,
                unchanged_record_ids=unchanged,
                summary=summary,
            )

    def auto_label(
        self, job_id: str, request: AutoLabelRequest
    ) -> AutoLabelingResult:
        with self._lock:
            self._require_mutable(job_id)
            dataframe, report = self._load_state(job_id)
            self._ensure_ai_audit_columns(dataframe)
            processed = 0
            skipped = 0
            counts = {"SELESAI": 0, "TINDAK_LANJUT": 0, "NEEDS_REVIEW": 0}

            for index, row in dataframe.iterrows():
                current_status = self._status_value(row.get("labeling_status"))
                if current_status != "UNLABELED" and not request.overwrite_existing:
                    skipped += 1
                    continue

                decision = classify_record(row)
                self._apply_label(
                    dataframe,
                    index,
                    decision.label,
                    decision.reason,
                    report,
                    "AUTO_LABEL",
                    validate_reason=False,
                    validator_role=AI_VALIDATOR_ROLE,
                    confidence=decision.confidence,
                    policy_version=POLICY_VERSION,
                )
                processed += 1
                counts[decision.label] += 1

            report["validator_role"] = AI_VALIDATOR_ROLE
            report["validator_roles"] = [AI_VALIDATOR_ROLE, VALIDATOR_ROLE]
            report["source_evidence_policy"] = (
                "Status sumber dan teks laporan digunakan oleh kebijakan AI-assisted "
                "yang versioned; status sumber dilarang menjadi fitur model."
            )
            executed_at = self._now()
            run_summary = {
                "policy_version": POLICY_VERSION,
                "validator_role": AI_VALIDATOR_ROLE,
                "processed_records": processed,
                "skipped_records": skipped,
                "decision_counts": counts,
                "overwrite_existing": request.overwrite_existing,
                "executed_at": executed_at,
            }
            report.setdefault("auto_labeling_runs", []).append(run_summary)
            current_statistics = self._statistics(dataframe)
            auto_events = [
                event
                for event in report.get("events", [])
                if event.get("operation") == "AUTO_LABEL"
            ]
            report["auto_labeling"] = {
                "policy_version": POLICY_VERSION,
                "validator_role": AI_VALIDATOR_ROLE,
                "identified_records": (
                    current_statistics["total_records"]
                    - current_statistics["unlabeled_records"]
                ),
                "decision_counts": {
                    "SELESAI": current_statistics["selesai_records"],
                    "TINDAK_LANJUT": current_statistics["tindak_lanjut_records"],
                    "NEEDS_REVIEW": current_statistics["needs_review_records"],
                },
                "first_identified_at": (
                    auto_events[0].get("created_at") if auto_events else executed_at
                ),
                "last_run": run_summary,
            }
            summary = self._persist(job_id, dataframe, report)
            return AutoLabelingResult(
                processed_records=processed,
                skipped_records=skipped,
                decision_counts=counts,
                policy_version=POLICY_VERSION,
                summary=summary,
            )

    def report(self, job_id: str) -> dict[str, Any]:
        _, report = self._load_state(job_id)
        return report

    def labeled_path(self, job_id: str) -> Path:
        path = self.jobs.labeled_dataset_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("dataset_labeled.xlsx")
        return path

    def _require_mutable(self, job_id: str) -> None:
        metadata = self.jobs.read_metadata(job_id)
        require_status_at_most(metadata.get("status"), JobStatus.LABELED, "labeling")

    def _load_state(self, job_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        labeled_path = self.jobs.labeled_dataset_path(job_id)
        report_path = self._report_path(job_id)
        if not labeled_path.is_file():
            raise ArtifactNotFoundError("dataset_labeled.xlsx")
        if not report_path.is_file():
            raise ArtifactNotFoundError("labeling_report.json")
        return self._read_labeled(labeled_path), read_json(report_path)

    def _read_labeled(self, path: Path) -> pd.DataFrame:
        try:
            dataframe = pd.read_excel(path, sheet_name="DATA_LABELED", dtype=object)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise InvalidDatasetError("Dataset labeled tidak dapat dibaca.") from error
        required = {"record_id", "keputusan_laporan", *LABEL_COLUMNS}
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise InvalidDatasetError(
                "Dataset labeled tidak valid; kolom hilang: " + ", ".join(missing) + "."
            )
        if dataframe["record_id"].duplicated().any():
            raise InvalidDatasetError("record_id pada dataset labeled harus unik.")
        return dataframe

    def _apply_label(
        self,
        dataframe: pd.DataFrame,
        index: Any,
        label: str,
        reason: str | None,
        report: dict[str, Any],
        operation: str,
        *,
        validate_reason: bool = True,
        validator_role: str = VALIDATOR_ROLE,
        confidence: float | None = None,
        policy_version: str | None = None,
    ) -> bool:
        if validate_reason:
            self._validate_relabel_reason(dataframe, [index], label, reason)
        previous_status = self._status_value(dataframe.at[index, "labeling_status"])
        previous_target = self._target_value(dataframe.at[index, "keputusan_laporan"])
        new_status = "NEEDS_REVIEW" if label == "NEEDS_REVIEW" else "LABELED"
        new_target = None if label == "NEEDS_REVIEW" else label
        if previous_status == new_status and previous_target == new_target:
            return False

        timestamp = self._now()
        dataframe.at[index, "labeling_status"] = new_status
        dataframe.at[index, "keputusan_laporan"] = new_target
        self._ensure_ai_audit_columns(dataframe)
        dataframe.at[index, "label_validator_role"] = validator_role
        dataframe.at[index, "label_updated_at"] = timestamp
        dataframe.at[index, "label_confidence"] = confidence
        dataframe.at[index, "label_decision_reason"] = (
            reason.strip() if reason and reason.strip() else None
        )
        dataframe.at[index, "label_policy_version"] = policy_version
        report.setdefault("events", []).append(
            {
                "event_type": "label_recorded",
                "operation": operation,
                "record_id": str(dataframe.at[index, "record_id"]),
                "previous_labeling_status": previous_status,
                "previous_target": previous_target,
                "new_labeling_status": new_status,
                "new_target": new_target,
                "validator_role": validator_role,
                "reason": reason.strip() if reason and reason.strip() else None,
                "confidence": confidence,
                "policy_version": policy_version,
                "created_at": timestamp,
            }
        )
        return True

    @staticmethod
    def _ensure_ai_audit_columns(dataframe: pd.DataFrame) -> None:
        for column in AI_AUDIT_COLUMNS:
            if column not in dataframe:
                dataframe[column] = None

    def _validate_relabel_reason(
        self,
        dataframe: pd.DataFrame,
        indexes: list[Any],
        new_label: str,
        reason: str | None,
    ) -> None:
        for index in indexes:
            previous_status = self._status_value(dataframe.at[index, "labeling_status"])
            previous_target = self._target_value(dataframe.at[index, "keputusan_laporan"])
            new_status = "NEEDS_REVIEW" if new_label == "NEEDS_REVIEW" else "LABELED"
            new_target = None if new_label == "NEEDS_REVIEW" else new_label
            is_changed_final = previous_status == "LABELED" and (
                previous_status != new_status or previous_target != new_target
            )
            if is_changed_final and not (reason and reason.strip()):
                raise InvalidDatasetError(
                    "Alasan wajib diisi ketika mengubah keputusan final yang sudah ada."
                )

    def _persist(
        self, job_id: str, dataframe: pd.DataFrame, report: dict[str, Any]
    ) -> LabelingSummary:
        report["updated_at"] = self._now()
        statistics = self._statistics(dataframe)
        training_ready, blockers = self._training_gate(statistics)
        report["statistics"] = statistics
        report["training_gate"] = {
            "ready": training_ready,
            "eligible_records": statistics["finalized_records"],
            "excluded_unlabeled": statistics["unlabeled_records"],
            "excluded_needs_review": statistics["needs_review_records"],
            "blockers": blockers,
        }
        job_status = (
            JobStatus.LABELED
            if statistics["finalized_records"] == statistics["total_records"]
            and statistics["total_records"] > 0
            else JobStatus.LABELING
        )

        write_excel_atomic(
            self.jobs.labeled_dataset_path(job_id), dataframe, "DATA_LABELED"
        )
        write_json_atomic(self._report_path(job_id), report)
        metadata = self.jobs.read_metadata(job_id)
        previous_status = parse_job_status(metadata.get("status"))
        updates: dict[str, Any] = {
            "status": job_status.value,
            "labeled_rows": statistics["finalized_records"],
            "needs_review_rows": statistics["needs_review_records"],
            "unlabeled_rows": statistics["unlabeled_records"],
            "labeling_updated_at": report["updated_at"],
            "training_ready": training_ready,
        }
        if JOB_STATUS_ORDER[job_status] < JOB_STATUS_ORDER[previous_status]:
            updates["status_reason"] = (
                "Keputusan label dibuka kembali untuk review dengan alasan yang diaudit."
            )
        else:
            updates["status_reason"] = None
        self.jobs.update_metadata(job_id, updates)
        return LabelingSummary(
            job_id=job_id,
            job_status=job_status.value,
            progress_percentage=round(
                statistics["finalized_records"]
                / statistics["total_records"]
                * 100,
                2,
            ),
            training_eligible_records=statistics["finalized_records"],
            training_ready=training_ready,
            training_blockers=blockers,
            updated_at=datetime.fromisoformat(report["updated_at"]),
            **statistics,
        )

    def _statistics(self, dataframe: pd.DataFrame) -> dict[str, int]:
        statuses = dataframe["labeling_status"].map(self._status_value)
        targets = dataframe["keputusan_laporan"].map(self._target_value)
        selesai = int((targets == "SELESAI").sum())
        tindak_lanjut = int((targets == "TINDAK_LANJUT").sum())
        return {
            "total_records": len(dataframe),
            "finalized_records": selesai + tindak_lanjut,
            "unlabeled_records": int((statuses == "UNLABELED").sum()),
            "needs_review_records": int((statuses == "NEEDS_REVIEW").sum()),
            "selesai_records": selesai,
            "tindak_lanjut_records": tindak_lanjut,
        }

    def _training_gate(self, statistics: dict[str, int]) -> tuple[bool, list[str]]:
        blockers: list[str] = []
        if statistics["finalized_records"] == 0:
            blockers.append("Belum ada keputusan final yang tervalidasi.")
        if statistics["selesai_records"] == 0 or statistics["tindak_lanjut_records"] == 0:
            blockers.append("Target training harus memiliki minimal dua kelas.")
        elif min(
            statistics["selesai_records"], statistics["tindak_lanjut_records"]
        ) < 2:
            blockers.append(
                "Setiap kelas memerlukan minimal dua sample untuk split yang valid."
            )
        return not blockers, blockers

    def _summary_from_state(
        self, job_id: str, dataframe: pd.DataFrame, report: dict[str, Any]
    ) -> LabelingSummary:
        statistics = self._statistics(dataframe)
        ready, blockers = self._training_gate(statistics)
        metadata = self.jobs.read_metadata(job_id)
        total = statistics["total_records"]
        return LabelingSummary(
            job_id=job_id,
            job_status=parse_job_status(metadata.get("status")).value,
            progress_percentage=round(
                statistics["finalized_records"] / total * 100, 2
            )
            if total
            else 0.0,
            training_eligible_records=statistics["finalized_records"],
            training_ready=ready,
            training_blockers=blockers,
            updated_at=datetime.fromisoformat(report["updated_at"]),
            **statistics,
        )

    def _filter(self, dataframe: pd.DataFrame, label_filter: str) -> pd.DataFrame:
        if label_filter == "ALL":
            return dataframe
        statuses = dataframe["labeling_status"].map(self._status_value)
        if label_filter in {"UNLABELED", "NEEDS_REVIEW"}:
            return dataframe.loc[statuses == label_filter]
        targets = dataframe["keputusan_laporan"].map(self._target_value)
        return dataframe.loc[targets == label_filter]

    def _report_path(self, job_id: str) -> Path:
        return self.jobs.report_path(job_id, "labeling_report.json")

    @staticmethod
    def _status_value(value: Any) -> str:
        text = "" if value is None or pd.isna(value) else str(value)
        return text if text in LABELING_STATUSES else "UNLABELED"

    @staticmethod
    def _target_value(value: Any) -> str | None:
        text = "" if value is None or pd.isna(value) else str(value)
        return text if text in VALID_FINAL_LABELS else None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
