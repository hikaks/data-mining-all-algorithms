from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PreprocessingResult(BaseModel):
    job_id: str
    status: str
    source_rows: int
    output_rows: int
    excluded_rows: int
    target_distribution: dict[str, int]
    near_duplicate_groups: int
    near_duplicate_pairs: int
    label_conflict_groups: int
    preprocessing_version: str
    completed_at: datetime


class PreprocessingReport(BaseModel):
    job_id: str
    generated_at: datetime
    preprocessing_version: str
    source_rows: int
    output_rows: int
    excluded_rows: int
    excluded_counts: dict[str, int]
    excluded_records: list[dict[str, Any]]
    target_distribution: dict[str, int]
    class_imbalance_ratio: float | None
    feature_contract: dict[str, Any]
    leakage_audit: dict[str, Any]
    transformer_spec: dict[str, Any]
    near_duplicate_evaluation: dict[str, Any]
    artifact_integrity: dict[str, str]
