from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas.common import SuccessResponse
from app.schemas.training import ModelMetadata, TrainingResult


router = APIRouter(tags=["Random Forest Training"])


@router.post(
    "/jobs/{job_id}/train",
    response_model=SuccessResponse[TrainingResult],
)
def train_model(request: Request, job_id: str) -> SuccessResponse[TrainingResult]:
    result = request.app.state.training_service.train(job_id)
    return SuccessResponse(data=result, message="Random Forest berhasil dilatih.")


@router.get(
    "/jobs/{job_id}/model-metadata",
    response_model=SuccessResponse[ModelMetadata],
)
def model_metadata(
    request: Request, job_id: str
) -> SuccessResponse[ModelMetadata]:
    result = request.app.state.experiment_service.services(job_id)['train'].metadata(job_id)
    return SuccessResponse(data=result, message="Metadata model berhasil dimuat.")


@router.get("/jobs/{job_id}/download/model", response_class=FileResponse)
def download_model(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.experiment_service.services(job_id)['train'].model_path(job_id)
    return FileResponse(
        path,
        filename="model_pipeline.joblib",
        media_type="application/octet-stream",
    )
