from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EvaluationResult(BaseModel):
    job_id: str
    status: str
    evaluation_id: str
    model_id: str
    evaluation_version: str
    evaluated_rows: int
    actual_distribution: dict[str, int]
    predicted_distribution: dict[str, int]
    accuracy: float
    balanced_accuracy: float
    positive_class: str | None
    positive_precision: float | None
    positive_recall: float | None
    positive_f1: float | None
    created_at: datetime


class EvaluationReport(BaseModel):
    job_id: str
    evaluation_id: str
    model_id: str
    created_at: datetime
    evaluation_version: str
    evaluation_scope: dict[str, Any]
    traceability: dict[str, Any]
    metrics: dict[str, Any]
    confusion_matrix: dict[str, Any]
    classification_report: dict[str, Any]
    prediction_audit: list[dict[str, Any]]
    feature_importance: dict[str, Any]
    limitations: list[str]


class FeatureImportanceReport(BaseModel):
    job_id: str
    evaluation_id: str
    model_id: str
    created_at: datetime
    method: str
    feature_count: int
    features: list[dict[str, Any]]
    limitations: list[str]
