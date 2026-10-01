from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SplitResult(BaseModel):
    job_id: str
    status: str
    strategy: str
    random_state: int
    train_rows: int
    test_rows: int
    actual_test_ratio: float
    train_distribution: dict[str, int]
    test_distribution: dict[str, int]
    group_overlap_count: int
    record_overlap_count: int
    split_version: str
    created_at: datetime


class SplitManifest(BaseModel):
    job_id: str
    created_at: datetime
    split_version: str
    source_artifact: dict[str, str]
    configuration: dict[str, Any]
    selection: dict[str, Any]
    train: dict[str, Any]
    test: dict[str, Any]
    validation: dict[str, Any]
    class_imbalance: dict[str, Any]
    candidate_summaries: list[dict[str, Any]]
