import json
import logging
import math
from pathlib import Path
import time
from threading import Lock
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ArtifactNotFoundError, InvalidDatasetError
from app.core.job_status import JobStatus, require_status_at_most
import pandas as pd

from app.schemas.cleaning import CleaningAuditPage, CleaningReport, CleaningResult
from app.schemas.dataset import DatasetPreview
from app.services.cleaning.pipeline import clean_dataset
from app.services.dataset_labels import DatasetLabelService
from app.storage.file_manager import read_json, write_excel_atomic, write_json_atomic
from app.storage.job_manager import JobManager
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.utils.excel import inspect_workbook
from app.utils.excel import dataframe_records


logger = logging.getLogger(__name__)
AUDIT_SECTIONS = {
    "invalid_dates",
    "incomplete_records",
    "duplicate_records",
    "operations",
    "removed_empty_records",
    "potential_duplicates",
}


class CleaningService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs = JobManager(settings.storage_root)
        self.labels = DatasetLabelService(settings)
        self.configuration = DatasetConfigurationService(settings)
        self._lock = CONFIGURATION_LOCK

    def clean(self, job_id: str) -> CleaningResult:
        with self._lock:
            config = self.configuration.get(job_id)
            if config['profile'] == 'generic':
                from app.services.generic_workflow import GenericWorkflowService
                return GenericWorkflowService(self.settings).clean(job_id)
            return self._clean(job_id)

    def _clean(self, job_id: str) -> CleaningResult:
        started_at = time.perf_counter()
        metadata = self.jobs.read_metadata(job_id)
        if metadata.get("status") == JobStatus.LABELED.value and self.jobs.report_path(job_id, "input_labels.json").is_file():
            for path in (self.jobs.cleaned_dataset_path(job_id), self.jobs.labeled_dataset_path(job_id), self.jobs.report_path(job_id, "labeling_report.json"), self.jobs.report_path(job_id, "cleaning_report.json")):
                if not path.is_file():
                    raise InvalidDatasetError("Artifact cleaning/label tidak lengkap; tidak boleh dibangun ulang di atas label yang sudah tersedia.")
            return self._result(read_json(self.jobs.report_path(job_id, "cleaning_report.json")))
        require_status_at_most(
            metadata.get("status", JobStatus.UPLOADED.value),
            JobStatus.CLEANED,
            "cleaning",
        )
        raw_path = self.jobs.raw_dataset_path(job_id)
        if not raw_path.is_file():
            raise InvalidDatasetError("Dataset mentah untuk job tidak ditemukan.")

        dataframe = inspect_workbook(
            raw_path, self.settings.required_sheet, self.settings.required_columns
        )
        output = clean_dataset(
            dataframe=dataframe,
            job_id=job_id,
            customer_mapping=self._load_mapping("customer_mapping.json"),
            technician_mapping=self._load_mapping("technician_mapping.json"),
            start_date=self.settings.data_start_date,
            cutoff_date=self.settings.data_cutoff_date,
        )
        cleaned_path = self.jobs.cleaned_dataset_path(job_id)
        report_path = self.jobs.report_path(job_id, "cleaning_report.json")
        self.labels.attach_cleaned(job_id, output.dataframe, output.report)
        output.report["decisions"]["target"] = "Label upload dipertahankan beserta alasan, role, confidence dan versi kebijakan; NEEDS_REVIEW dikecualikan dari training."
        output.report["missing_values"]["keputusan_laporan"] = int(output.dataframe["keputusan_laporan"].isna().sum())
        write_excel_atomic(cleaned_path, output.dataframe, "DATA_CLEANED")
        write_json_atomic(report_path, output.report)
        self.jobs.update_metadata(
            job_id,
            {
                "status": JobStatus.CLEANED.value,
                "cleaned_rows": len(output.dataframe),
                "cleaned_at": output.report["generated_at"],
            },
        )
        self.labels.persist_cleaned_labels(job_id, output.dataframe)
        logger.info(
            "Dataset cleaned job_id=%s operation=cleaning status=LABELED duration=%.3f",
            job_id,
            time.perf_counter() - started_at,
        )
        return self._result(output.report)

    @staticmethod
    def _result(report: dict[str, Any]) -> CleaningResult:
        removed = report["removed"]
        return CleaningResult(
            job_id=report["job_id"],
            status=JobStatus.LABELED.value,
            rows_before=report["rows_before"],
            rows_after=report["rows_after"],
            empty_rows_removed=removed["empty_rows"],
            duplicates_removed=removed["duplicates"],
            invalid_dates=len(report["invalid_dates"]),
            incomplete_rows=len(report["incomplete_records"]),
            cleaned_at=report["generated_at"],
        )

    def report(self, job_id: str) -> CleaningReport:
        self.configuration.get(job_id)
        report_path = self.jobs.report_path(job_id, "cleaning_report.json")
        if not report_path.is_file():
            raise ArtifactNotFoundError("cleaning_report.json")
        return CleaningReport.model_validate(read_json(report_path))

    def preview(self, job_id: str, page: int, page_size: int) -> DatasetPreview:
        path = self.cleaned_path(job_id)
        try:
            dataframe = pd.read_excel(path, sheet_name="DATA_CLEANED", dtype=object, keep_default_na=False)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise InvalidDatasetError("Dataset bersih tidak dapat dibaca.") from error
        total_rows = len(dataframe)
        start = (page - 1) * page_size
        return DatasetPreview(
            page=page,
            page_size=page_size,
            total_rows=total_rows,
            total_pages=math.ceil(total_rows / page_size) if total_rows else 0,
            columns=[str(column) for column in dataframe.columns],
            items=dataframe_records(dataframe.iloc[start : start + page_size]),
        )

    def audit_page(
        self, job_id: str, section: str, page: int, page_size: int
    ) -> CleaningAuditPage:
        if section not in AUDIT_SECTIONS:
            raise InvalidDatasetError(
                "Bagian audit tidak valid. Gunakan salah satu: "
                + ", ".join(sorted(AUDIT_SECTIONS))
                + "."
            )
        report_path = self.jobs.report_path(job_id, "cleaning_report.json")
        if not report_path.is_file():
            raise ArtifactNotFoundError("cleaning_report.json")
        report = read_json(report_path)
        items = report[section]
        total_items = len(items)
        start = (page - 1) * page_size
        return CleaningAuditPage(
            section=section,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=math.ceil(total_items / page_size) if total_items else 0,
            items=items[start : start + page_size],
        )

    def cleaned_path(self, job_id: str) -> Path:
        path = self.jobs.cleaned_dataset_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("dataset_cleaned.xlsx")
        return path

    def raw_path(self, job_id: str) -> Path:
        path = self.jobs.raw_dataset_path(job_id)
        if not path.is_file():
            raise ArtifactNotFoundError("dataset.xlsx")
        return path

    def _load_mapping(self, filename: str) -> dict[str, str]:
        path = self.settings.mapping_config_root / filename
        try:
            with path.open("r", encoding="utf-8") as file_handle:
                payload: Any = json.load(file_handle)
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidDatasetError(
                f"Konfigurasi mapping '{filename}' tidak dapat dibaca."
            ) from error
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise InvalidDatasetError(f"Konfigurasi mapping '{filename}' tidak valid.")
        return payload
