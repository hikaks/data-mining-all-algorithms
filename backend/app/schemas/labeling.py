from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


LabelValue = Literal["SELESAI", "TINDAK_LANJUT", "NEEDS_REVIEW"]
LabelFilter = Literal[
    "ALL", "UNLABELED", "SELESAI", "TINDAK_LANJUT", "NEEDS_REVIEW"
]


class LabelUpdateRequest(BaseModel):
    label: LabelValue
    reason: str | None = Field(default=None, max_length=500)


class BulkLabelRequest(BaseModel):
    record_ids: list[str] = Field(min_length=1, max_length=100)
    label: LabelValue
    reason: str | None = Field(default=None, max_length=500)


class AutoLabelRequest(BaseModel):
    overwrite_existing: bool = False


class LabelingSummary(BaseModel):
    job_id: str
    job_status: str
    total_records: int
    finalized_records: int
    unlabeled_records: int
    needs_review_records: int
    selesai_records: int
    tindak_lanjut_records: int
    progress_percentage: float
    training_eligible_records: int
    training_ready: bool
    training_blockers: list[str]
    updated_at: datetime


class LabelingPage(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    label_filter: str
    items: list[dict[str, Any]]


class LabelingMutationResult(BaseModel):
    updated_record_ids: list[str]
    unchanged_record_ids: list[str]
    summary: LabelingSummary


class AutoLabelingResult(BaseModel):
    processed_records: int
    skipped_records: int
    decision_counts: dict[str, int]
    policy_version: str
    summary: LabelingSummary
