from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from app.schemas.cleaning import CleaningAuditPage, CleaningReport, CleaningResult
from app.schemas.common import SuccessResponse
from app.schemas.dataset import DatasetPreview


router = APIRouter(tags=["Cleaning"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post(
    "/jobs/{job_id}/clean", response_model=SuccessResponse[CleaningResult]
)
def clean_dataset(request: Request, job_id: str) -> SuccessResponse[CleaningResult]:
    result = request.app.state.cleaning_service.clean(job_id)
    return SuccessResponse(data=result, message="Dataset berhasil dibersihkan.")


@router.get(
    "/jobs/{job_id}/cleaning-report",
    response_model=SuccessResponse[CleaningReport],
)
def cleaning_report(
    request: Request, job_id: str, include_details: bool = True
) -> SuccessResponse[CleaningReport]:
    result = request.app.state.cleaning_service.report(job_id)
    if not include_details:
        result = result.model_copy(update={
            section: [] for section in (
                "invalid_dates", "incomplete_records", "duplicate_records", "operations",
                "removed_empty_records", "potential_duplicates",
            )
        })
    return SuccessResponse(data=result, message="Laporan cleaning berhasil dimuat.")


@router.get(
    "/jobs/{job_id}/cleaned/preview",
    response_model=SuccessResponse[DatasetPreview],
)
def cleaned_preview(
    request: Request,
    job_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SuccessResponse[DatasetPreview]:
    result = request.app.state.cleaning_service.preview(job_id, page, page_size)
    return SuccessResponse(data=result, message="Preview dataset bersih berhasil dimuat.")


@router.get(
    "/jobs/{job_id}/cleaning-report/audit",
    response_model=SuccessResponse[CleaningAuditPage],
)
def cleaning_audit(
    request: Request,
    job_id: str,
    section: Literal[
        "invalid_dates",
        "incomplete_records",
        "duplicate_records",
        "operations",
        "removed_empty_records",
        "potential_duplicates",
    ],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SuccessResponse[CleaningAuditPage]:
    result = request.app.state.cleaning_service.audit_page(
        job_id, section, page, page_size
    )
    return SuccessResponse(data=result, message="Audit cleaning berhasil dimuat.")


@router.get("/jobs/{job_id}/download/raw", response_class=FileResponse)
def download_raw(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.cleaning_service.raw_path(job_id)
    return FileResponse(path, filename=path.name, media_type='text/csv; charset=utf-8' if path.suffix == '.csv' else XLSX_MEDIA_TYPE)


@router.get("/jobs/{job_id}/download/cleaned", response_class=FileResponse)
def download_cleaned(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.cleaning_service.cleaned_path(job_id)
    return FileResponse(
        path, filename="dataset_cleaned.xlsx", media_type=XLSX_MEDIA_TYPE
    )
