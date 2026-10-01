from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import FileResponse

from app.schemas.common import SuccessResponse
from app.schemas.prediction import (
    ActualDecisionRequest,
    PredictionHistoryItem,
    PredictionHistoryPage,
    PredictionRequest,
    PredictionResult,
    GenericPredictionRequest,
)


router = APIRouter(tags=["Prediction"])


@router.post(
    "/jobs/{job_id}/predict",
    response_model=SuccessResponse[PredictionResult],
)
def predict(
    request: Request, job_id: str, payload: PredictionRequest | GenericPredictionRequest
) -> SuccessResponse[PredictionResult]:
    result = request.app.state.prediction_service.predict(job_id, payload)
    return SuccessResponse(
        data=result,
        message="Prediction berhasil dibuat sebagai rekomendasi model.",
    )


@router.get('/jobs/{job_id}/prediction/schema')
def prediction_schema(request: Request, job_id: str):
    return SuccessResponse(data=request.app.state.prediction_service.schema(job_id), message='Schema input model tersimpan.')


@router.get(
    "/jobs/{job_id}/predictions",
    response_model=SuccessResponse[PredictionHistoryPage],
)
def prediction_history(
    request: Request,
    job_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> SuccessResponse[PredictionHistoryPage]:
    result = request.app.state.prediction_service.history(job_id, page, page_size)
    return SuccessResponse(data=result, message="Histori prediction berhasil dimuat.")


@router.patch(
    "/jobs/{job_id}/predictions/{prediction_id}/actual-decision",
    response_model=SuccessResponse[PredictionHistoryItem],
)
def record_actual_decision(
    request: Request,
    job_id: str,
    prediction_id: Annotated[
        str, Path(pattern=r"^PRED-[A-F0-9]{16}$")
    ],
    payload: ActualDecisionRequest,
) -> SuccessResponse[PredictionHistoryItem]:
    result = request.app.state.prediction_service.record_actual_decision(
        job_id, prediction_id, payload
    )
    return SuccessResponse(data=result, message="Keputusan aktual berhasil dicatat.")


@router.get("/jobs/{job_id}/download/predictions", response_class=FileResponse)
def download_prediction_history(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.prediction_service.history_path(job_id)
    return FileResponse(
        path,
        filename="predictions.jsonl",
        media_type="application/x-ndjson",
    )
