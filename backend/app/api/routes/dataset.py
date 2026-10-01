from typing import Annotated

from fastapi import APIRouter, File, Query, Request, UploadFile

from app.schemas.common import SuccessResponse
from app.schemas.dataset import DatasetConfigurationRequest, DatasetPreview, DatasetSummary, DatasetUploadResult, JobOverview


router = APIRouter(tags=["Dataset"])


@router.get("/jobs/{job_id}", response_model=SuccessResponse[JobOverview])
def job_overview(request: Request, job_id: str) -> SuccessResponse[JobOverview]:
    result = request.app.state.dataset_service.overview(job_id)
    return SuccessResponse(data=result, message="Status job berhasil dimuat tanpa mengubah data.")


@router.post(
    "/dataset/upload",
    response_model=SuccessResponse[DatasetUploadResult],
    status_code=201,
)
async def upload_dataset(
    request: Request,
    file: Annotated[UploadFile, File(description="Dataset tabular (.xlsx atau .csv)")],
) -> SuccessResponse[DatasetUploadResult]:
    result = await request.app.state.dataset_service.upload(file)
    return SuccessResponse(data=result, message="Dataset diunggah. Pilih target dan fitur sebelum melanjutkan.")


@router.get("/jobs/{job_id}/dataset/schema")
def dataset_schema(request: Request, job_id: str, sheet_name: str | None = None, delimiter: str | None = None, target_column: str | None = None):
    result = request.app.state.dataset_configuration.schema(job_id, sheet_name, delimiter, target_column)
    return SuccessResponse(data=result, message="Schema dataset berhasil dibaca.")


@router.get("/jobs/{job_id}/dataset/configuration")
def dataset_configuration(request: Request, job_id: str):
    return SuccessResponse(data=request.app.state.dataset_configuration.get(job_id), message="Konfigurasi berhasil dibaca.")


@router.put("/jobs/{job_id}/dataset/configuration")
def save_dataset_configuration(request: Request, job_id: str, payload: DatasetConfigurationRequest):
    return SuccessResponse(data=request.app.state.dataset_configuration.save(job_id, payload), message="Target dan fitur disimpan. Lanjutkan cleaning.")


@router.get(
    "/jobs/{job_id}/dataset/preview",
    response_model=SuccessResponse[DatasetPreview],
)
def preview_dataset(
    request: Request,
    job_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SuccessResponse[DatasetPreview]:
    result = request.app.state.dataset_service.preview(job_id, page, page_size)
    return SuccessResponse(data=result, message="Preview dataset berhasil dimuat.")


@router.get(
    "/jobs/{job_id}/dataset/summary",
    response_model=SuccessResponse[DatasetSummary],
)
def dataset_summary(
    request: Request, job_id: str
) -> SuccessResponse[DatasetSummary]:
    result = request.app.state.dataset_service.summary(job_id)
    return SuccessResponse(data=result, message="Ringkasan dataset berhasil dihitung.")
