from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FeatureSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    kind: Literal["numeric", "categorical", "text", "date"]


class DatasetConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal["generic", "maxkomp"] = "generic"
    sheet_name: str | None = None
    delimiter: Literal[",", ";", "\t"] | None = None
    target_column: str = Field(min_length=1)
    features: list[FeatureSelection] = Field(default_factory=list)


class DatasetUploadResult(BaseModel):
    job_id: str
    original_filename: str
    status: str
    sheet_name: str | None
    row_count: int
    column_count: int
    columns: list[str]
    created_at: datetime
    file_format: str = "xlsx"
    sheets: list[str] = Field(default_factory=list)
    configuration_ready: bool = False


class JobOverview(BaseModel):
    active_experiment_id: str | None = None
    experiment_count: int = 0
    prediction_ready: bool = False
    job_id: str
    original_filename: str
    status: str
    created_at: datetime
    sheet_name: str | None = None
    raw_rows: int = 0
    raw_columns: int = 0
    cleaned_rows: int = 0
    labeled_rows: int = 0
    needs_review_rows: int = 0
    preprocessed_rows: int = 0
    split_train_rows: int = 0
    split_test_rows: int = 0
    model_id: str | None = None
    input_label_source: str | None = None
    input_label_counts: dict[str, int] = Field(default_factory=dict)
    training_ready: bool = False
    file_format: str = "xlsx"
    sheets: list[str] = Field(default_factory=list)
    configuration_ready: bool = True
    profile: str | None = None
    target_column: str | None = None
    artifacts: dict[str, bool]


class DatasetPreview(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    columns: list[str]
    items: list[dict[str, Any]]


class ColumnSummary(BaseModel):
    name: str
    dtype: str
    missing_count: int
    missing_percentage: float
    non_missing_count: int
    unique_count: int


class DatasetSummary(BaseModel):
    job_id: str
    sheet_name: str
    row_count: int
    column_count: int
    duplicate_rows: int
    operationally_empty_rows: int
    date_range: dict[str, Any]
    distributions: dict[str, list[dict[str, Any]]]
    columns: list[ColumnSummary]
    generated_at: datetime


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
