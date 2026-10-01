from datetime import datetime, timezone
from pathlib import Path
import re
import secrets
from typing import Any

from app.core.exceptions import JobNotFoundError
from app.core.job_status import JobStatus
from app.storage.file_manager import read_json, write_json_atomic


JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
JOB_DIRECTORIES = (
    "raw",
    "cleaned",
    "labeled",
    "preprocessed",
    "model",
    "reports",
    "predictions",
    "config",
)


class JobManager:
    def __init__(self, storage_root: Path) -> None:
        self.jobs_root = storage_root / "jobs"

    def create_job(self, original_filename: str) -> dict[str, Any]:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        while True:
            job_id = secrets.token_urlsafe(16)
            job_path = self.jobs_root / job_id
            try:
                job_path.mkdir(exist_ok=False)
                break
            except FileExistsError:
                continue

        for directory in JOB_DIRECTORIES:
            (job_path / directory).mkdir()

        metadata: dict[str, Any] = {
            "job_id": job_id,
            "original_filename": original_filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": JobStatus.UPLOADED.value,
            "raw_rows": 0,
            "cleaned_rows": 0,
            "target_column": "keputusan_laporan",
            "train_ratio": 0.8,
            "test_ratio": 0.2,
        }
        write_json_atomic(job_path / "config" / "job.json", metadata)
        return metadata

    def require_job_path(self, job_id: str) -> Path:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise JobNotFoundError(job_id)
        job_path = self.jobs_root / job_id
        if not job_path.is_dir():
            raise JobNotFoundError(job_id)
        return job_path

    def read_metadata(self, job_id: str) -> dict[str, Any]:
        job_path = self.require_job_path(job_id)
        return read_json(job_path / "config" / "job.json")

    def update_metadata(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        job_path = self.require_job_path(job_id)
        metadata = read_json(job_path / "config" / "job.json")
        metadata.update(updates)
        write_json_atomic(job_path / "config" / "job.json", metadata)
        return metadata

    def raw_dataset_path(self, job_id: str) -> Path:
        metadata = self.read_metadata(job_id)
        suffix = "csv" if metadata.get("file_format") == "csv" else "xlsx"
        return self.require_job_path(job_id) / "raw" / f"dataset.{suffix}"

    def cleaned_dataset_path(self, job_id: str) -> Path:
        return self.require_job_path(job_id) / "cleaned" / "dataset_cleaned.xlsx"

    def labeled_dataset_path(self, job_id: str) -> Path:
        return self.require_job_path(job_id) / "labeled" / "dataset_labeled.xlsx"

    def preprocessed_dataset_path(self, job_id: str) -> Path:
        directory = self.require_job_path(job_id) / "preprocessed"
        directory.mkdir(exist_ok=True)
        return directory / "dataset_preprocessed.xlsx"

    def model_pipeline_path(self, job_id: str) -> Path:
        return self.require_job_path(job_id) / "model" / "model_pipeline.joblib"

    def model_metadata_path(self, job_id: str) -> Path:
        return self.require_job_path(job_id) / "model" / "model_metadata.json"

    def prediction_history_path(self, job_id: str) -> Path:
        return self.require_job_path(job_id) / "predictions" / "predictions.jsonl"

    def report_path(self, job_id: str, filename: str) -> Path:
        return self.require_job_path(job_id) / "reports" / filename

    def delete_job(self, job_id: str) -> None:
        job_path = self.require_job_path(job_id)
        for path in sorted(job_path.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        job_path.rmdir()
