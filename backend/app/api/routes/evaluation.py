from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas.common import SuccessResponse
from app.schemas.evaluation import (
    EvaluationReport,
    EvaluationResult,
    FeatureImportanceReport,
)


router = APIRouter(tags=["Model Evaluation"])


@router.post(
    "/jobs/{job_id}/evaluate",
    response_model=SuccessResponse[EvaluationResult],
)
def evaluate_model(
    request: Request, job_id: str
) -> SuccessResponse[EvaluationResult]:
    result = request.app.state.evaluation_service.evaluate(job_id)
    return SuccessResponse(data=result, message="Evaluasi model berhasil dibuat.")


@router.get(
    "/jobs/{job_id}/evaluation",
    response_model=SuccessResponse[EvaluationReport],
)
def evaluation_report(
    request: Request, job_id: str
) -> SuccessResponse[EvaluationReport]:
    result = request.app.state.experiment_service.services(job_id)['evaluate'].report(job_id)
    return SuccessResponse(data=result, message="Laporan evaluasi berhasil dimuat.")


@router.get(
    "/jobs/{job_id}/feature-importance",
    response_model=SuccessResponse[FeatureImportanceReport],
)
def feature_importance(
    request: Request, job_id: str
) -> SuccessResponse[FeatureImportanceReport]:
    result = request.app.state.experiment_service.services(job_id)['evaluate'].feature_importance(job_id)
    return SuccessResponse(data=result, message="Feature importance berhasil dimuat.")


@router.get("/jobs/{job_id}/download/evaluation", response_class=FileResponse)
def download_evaluation(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.experiment_service.services(job_id)['evaluate'].evaluation_path(job_id)
    return FileResponse(path, filename="evaluation.json", media_type="application/json")


@router.get(
    "/jobs/{job_id}/download/feature-importance", response_class=FileResponse
)
def download_feature_importance(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.experiment_service.services(job_id)['evaluate'].feature_importance_path(job_id)
    return FileResponse(
        path, filename="feature_importance.json", media_type="application/json"
    )
