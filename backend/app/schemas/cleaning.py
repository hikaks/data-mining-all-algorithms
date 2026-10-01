from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CleaningResult(BaseModel):
    job_id: str
    status: str
    rows_before: int
    rows_after: int
    empty_rows_removed: int
    duplicates_removed: int
    invalid_dates: int
    incomplete_rows: int
    cleaned_at: datetime


class CleaningReport(BaseModel):
    job_id: str
    generated_at: datetime
    rows_before: int
    rows_after: int
    removed: dict[str, int]
    normalization: dict[str, int | dict[str, str]]
    missing_values: dict[str, int]
    invalid_dates: list[dict[str, Any]]
    incomplete_records: list[dict[str, Any]]
    duplicate_records: list[dict[str, Any]]
    operations: list[dict[str, Any]]
    removed_empty_records: list[dict[str, Any]]
    potential_duplicates: list[dict[str, Any]]
    near_duplicate_evaluation: dict[str, Any]
    decisions: dict[str, str]


class CleaningAuditPage(BaseModel):
    section: str
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[dict[str, Any]]
