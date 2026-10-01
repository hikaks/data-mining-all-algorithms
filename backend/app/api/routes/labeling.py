from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from app.schemas.common import SuccessResponse
from app.schemas.labeling import (
    LabelFilter,
    LabelingPage,
    LabelingSummary,
)


router = APIRouter(tags=["Dataset Label Audit (read-only)"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/jobs/{job_id}/labeling/summary",
    response_model=SuccessResponse[LabelingSummary],
)
def labeling_summary(
    request: Request, job_id: str
) -> SuccessResponse[LabelingSummary]:
    result = request.app.state.labeling_service.summary(job_id)
    return SuccessResponse(data=result, message="Progress labeling berhasil dimuat.")


@router.get(
    "/jobs/{job_id}/labeling/records",
    response_model=SuccessResponse[LabelingPage],
)
def labeling_records(
    request: Request,
    job_id: str,
    label_filter: LabelFilter = "ALL",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> SuccessResponse[LabelingPage]:
    result = request.app.state.labeling_service.records(
        job_id, label_filter, page, page_size
    )
    return SuccessResponse(data=result, message="Record labeling berhasil dimuat.")


@router.get(
    "/jobs/{job_id}/labeling/report",
    response_model=SuccessResponse[dict[str, Any]],
)
def labeling_report(
    request: Request, job_id: str, limit: Annotated[int | None, Query(ge=1, le=100)] = None
) -> SuccessResponse[dict[str, Any]]:
    result = request.app.state.labeling_service.report(job_id)
    if limit is not None:
        result = {**result, "events": result.get("events", [])[-limit:]}
    return SuccessResponse(data=result, message="Audit labeling berhasil dimuat.")


@router.get("/jobs/{job_id}/download/labeled", response_class=FileResponse)
def download_labeled(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.labeling_service.labeled_path(job_id)
    return FileResponse(
        path, filename="dataset_labeled.xlsx", media_type=XLSX_MEDIA_TYPE
    )
