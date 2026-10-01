from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FinalDecision = str


class GenericPredictionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    features: dict[str, Any]


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tanggal: date
    customer: str = Field(min_length=1, max_length=200)
    teknisi: str = Field(default="UNKNOWN", min_length=1, max_length=500)
    text_laporan: str = Field(min_length=3, max_length=10_000)


class PredictionResult(BaseModel):
    experiment_id: str = 'legacy'
    prediction_id: str
    model_id: str
    created_at: datetime
    prediction: FinalDecision
    confidence: float
    probabilities: dict[str, float]
    recommendation_only: bool
    warning: str
    actual_decision: FinalDecision | None = None


class ActualDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    actual_decision: FinalDecision = Field(min_length=1, max_length=1000)
    reason: str | None = Field(default=None, max_length=500)


class PredictionHistoryItem(BaseModel):
    experiment_id: str = 'legacy'
    prediction_id: str
    model_id: str
    created_at: datetime
    input: dict[str, Any]
    prediction: FinalDecision
    confidence: float
    probabilities: dict[str, float]
    recommendation_only: bool
    warning: str
    actual_decision: FinalDecision | None = None
    actual_decision_recorded_at: datetime | None = None
    actual_decision_reason: str | None = None
    validator_role: str | None = None


class PredictionHistoryPage(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    event_count: int
    items: list[PredictionHistoryItem]
