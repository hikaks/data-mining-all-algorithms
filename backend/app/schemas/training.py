from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TrainingResult(BaseModel):
    job_id: str
    status: str
    model_id: str
    algorithm: str
    training_version: str
    trained_rows: int
    train_distribution: dict[str, int]
    classes: list[str]
    transformed_feature_count: int
    training_seconds: float
    created_at: datetime


class ModelMetadata(BaseModel):
    job_id: str
    model_id: str
    created_at: datetime
    training_version: str
    algorithm: str
    target: dict[str, Any]
    configuration: dict[str, Any]
    feature_contract: dict[str, Any]
    training_data: dict[str, Any]
    artifacts: dict[str, Any]
    dependencies: dict[str, str]
    verification: dict[str, Any]
