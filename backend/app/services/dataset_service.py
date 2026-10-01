from datetime import datetime
import logging
import math
from pathlib import Path
import time
from hashlib import sha256

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import AppError, InvalidDatasetError
from app.core.job_status import JobStatus, advance_job_status
from app.schemas.dataset import DatasetPreview, DatasetSummary, DatasetUploadResult, JobOverview
from app.services.data_understanding_service import build_summary, summary_to_json
from app.services.dataset_configuration import DatasetConfigurationService
from app.storage.file_manager import read_json, write_bytes_atomic, write_json_atomic
from app.storage.job_manager import JobManager
from app.utils.excel import dataframe_records, inspect_workbook
from app.utils.tabular import inspect_input, read_input, missing


logger = logging.getLogger(__name__)


class DatasetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)

    def overview(self, job_id: str) -> JobOverview:
        """Read status and artifact availability without initializing or changing a job."""
        job_path = self.jobs.require_job_path(job_id)
        metadata = self.jobs.read_metadata(job_id)
        artifact_paths = {
            "raw": str(self.jobs.raw_dataset_path(job_id).relative_to(job_path)),
            "understanding": "reports/data_understanding.json",
            "cleaned": "cleaned/dataset_cleaned.xlsx",
            "labeled": "labeled/dataset_labeled.xlsx",
            "preprocessed": "preprocessed/dataset_preprocessed.xlsx",
            "split": "reports/split_manifest.json",
            "model": "model/model_pipeline.joblib",
            "evaluation": "reports/evaluation.json",
            "predictions": "predictions/predictions.jsonl",
        }
        from app.services.experiment_service import ExperimentService
        from app.storage.experiments import artifact_jobs
        experiments = ExperimentService(self.settings).list(job_id)
        items = experiments['items']
        active = experiments['active_experiment_id']
        availability = {name: (job_path / path).is_file() for name, path in artifact_paths.items()}
        for name, state in [('split', 'SPLIT_READY'), ('model', 'TRAINED'), ('evaluation', 'EVALUATED')]:
            rank = {'CREATED': 0, 'SPLIT_READY': 1, 'TRAINED': 2, 'EVALUATED': 3}
            availability[name] = availability[name] or any(rank[item['status']] >= rank[state] for item in items)
        if availability['evaluation']:
            metadata['status'] = advance_job_status(metadata['status'], JobStatus.EVALUATED).value
        elif availability['model']:
            metadata['status'] = advance_job_status(metadata['status'], JobStatus.TRAINED).value
        if active:
            active_jobs = artifact_jobs(self.settings.storage_root, job_id)
            metadata['model_id'] = read_json(active_jobs.model_metadata_path(job_id))['model_id']
        split_item = next((item for item in items if item['experiment_id'] == active), None)
        if split_item is None:
            split_item = next((item for item in items if item.get('actual_test_ratio') is not None), None)
        if split_item:
            split_jobs = artifact_jobs(self.settings.storage_root, job_id, split_item['experiment_id'])
            manifest = read_json(split_jobs.report_path(job_id, 'split_manifest.json'))
            metadata['split_train_rows'] = manifest['train']['row_count']
            metadata['split_test_rows'] = manifest['test']['row_count']
        return JobOverview(
            **metadata,
            artifacts=availability, active_experiment_id=active, experiment_count=len(items), prediction_ready=active is not None,
        )

    async def upload(self, upload: UploadFile) -> DatasetUploadResult:
        started_at = time.perf_counter()
        original_filename = Path(upload.filename or "").name
        try:
            if not original_filename:
                raise InvalidDatasetError("Nama file tidak tersedia.")
            if Path(original_filename).suffix.lower() not in {".xlsx", ".csv"}:
                raise InvalidDatasetError("File harus menggunakan extension .xlsx atau .csv.")
            content = await self._read_bounded(upload)
        finally:
            await upload.close()

        metadata = self.jobs.create_job(original_filename)
        job_id = str(metadata["job_id"])
        self.jobs.update_metadata(job_id, {"file_format": Path(original_filename).suffix.lower()[1:], "configuration_ready": False, "target_column": None})
        raw_path = self.jobs.raw_dataset_path(job_id)
        try:
            write_bytes_atomic(raw_path, content)
            input_info = inspect_input(raw_path)
            dataframe = None
            last_error = None
            for sheet in input_info["sheets"] or [None]:
                try:
                    dataframe = read_input(raw_path, sheet, input_info["delimiter"])
                    input_info["sheet_name"] = sheet
                    break
                except InvalidDatasetError as error:
                    last_error = error
            if dataframe is None:
                raise last_error or InvalidDatasetError("Tidak ada sheet dataset yang valid.")
            updated = self.jobs.update_metadata(
                job_id,
                {
                    "status": JobStatus.UPLOADED.value,
                    "raw_rows": len(dataframe),
                    "raw_columns": len(dataframe.columns),
                    **input_info,
                },
            )
        except Exception as error:
            self.jobs.delete_job(job_id)
            logger.warning(
                "Dataset upload failed job_id=%s operation=upload error=%s",
                job_id,
                type(error).__name__,
            )
            if isinstance(error, AppError):
                raise
            raise InvalidDatasetError("Dataset gagal divalidasi.") from error
        logger.info(
            "Dataset uploaded job_id=%s operation=upload status=UPLOADED duration=%.3f",
            job_id,
            time.perf_counter() - started_at,
        )
        return DatasetUploadResult(
            job_id=job_id,
            original_filename=original_filename,
            status=str(updated["status"]),
            sheet_name=input_info["sheet_name"],
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            columns=[str(column) for column in dataframe.columns],
            created_at=datetime.fromisoformat(str(updated["created_at"])),
            file_format=Path(original_filename).suffix.lower()[1:],
            sheets=input_info["sheets"],
            configuration_ready=False,
        )

    def preview(self, job_id: str, page: int, page_size: int) -> DatasetPreview:
        dataframe = self._load_raw_dataset(job_id)
        total_rows = len(dataframe)
        start = (page - 1) * page_size
        page_frame = dataframe.iloc[start : start + page_size]
        return DatasetPreview(
            page=page,
            page_size=page_size,
            total_rows=total_rows,
            total_pages=math.ceil(total_rows / page_size),
            columns=[str(column) for column in dataframe.columns],
            items=dataframe_records(page_frame),
        )

    def summary(self, job_id: str) -> DatasetSummary:
        self.configuration.get(job_id)
        path = self.jobs.report_path(job_id, "data_understanding.json")
        return DatasetSummary.model_validate(read_json(path))

    async def _read_bounded(self, upload: UploadFile) -> bytes:
        content = bytearray()
        chunk_size = 1024 * 1024
        while chunk := await upload.read(chunk_size):
            content.extend(chunk)
            if len(content) > self.settings.max_upload_bytes:
                raise InvalidDatasetError(
                    "Ukuran file melebihi batas upload yang dikonfigurasi."
                )
        if not content:
            raise InvalidDatasetError("File upload kosong.")
        return bytes(content)

    def _load_raw_dataset(self, job_id: str):
        raw_path = self.jobs.raw_dataset_path(job_id)
        if not raw_path.is_file():
            raise InvalidDatasetError("Dataset mentah untuk job tidak ditemukan.")
        metadata = self.jobs.read_metadata(job_id)
        frame = read_input(raw_path, metadata.get("sheet_name"), metadata.get("delimiter"))
        return frame.map(lambda value: None if missing(value) else value)
