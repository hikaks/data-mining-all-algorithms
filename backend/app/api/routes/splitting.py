from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas.common import SuccessResponse
from app.schemas.splitting import SplitManifest, SplitResult


router = APIRouter(tags=["Train/Test Split"])


@router.post(
    "/jobs/{job_id}/split",
    response_model=SuccessResponse[SplitResult],
)
def create_split(request: Request, job_id: str) -> SuccessResponse[SplitResult]:
    result = request.app.state.split_service.create_split(job_id)
    return SuccessResponse(data=result, message="Train/test split berhasil dibuat.")


@router.get(
    "/jobs/{job_id}/split-manifest",
    response_model=SuccessResponse[SplitManifest],
)
def split_manifest(
    request: Request, job_id: str
) -> SuccessResponse[SplitManifest]:
    result = request.app.state.experiment_service.services(job_id)['split'].manifest(job_id)
    return SuccessResponse(data=result, message="Split manifest berhasil dimuat.")


@router.get("/jobs/{job_id}/download/split-manifest", response_class=FileResponse)
def download_split_manifest(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.experiment_service.services(job_id)['split'].manifest_path(job_id)
    return FileResponse(
        path, filename="split_manifest.json", media_type="application/json"
    )
