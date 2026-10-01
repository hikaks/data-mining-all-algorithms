from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas.common import SuccessResponse
from app.schemas.preprocessing import PreprocessingReport, PreprocessingResult


router = APIRouter(tags=["Preprocessing"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post(
    "/jobs/{job_id}/preprocess",
    response_model=SuccessResponse[PreprocessingResult],
)
def preprocess(
    request: Request, job_id: str
) -> SuccessResponse[PreprocessingResult]:
    result = request.app.state.preprocessing_service.preprocess(job_id)
    return SuccessResponse(data=result, message="Preprocessing berhasil diselesaikan.")


@router.get(
    "/jobs/{job_id}/preprocessing-report",
    response_model=SuccessResponse[PreprocessingReport],
)
def preprocessing_report(
    request: Request, job_id: str
) -> SuccessResponse[PreprocessingReport]:
    result = request.app.state.preprocessing_service.report(job_id)
    return SuccessResponse(data=result, message="Laporan preprocessing berhasil dimuat.")


@router.get("/jobs/{job_id}/download/preprocessed", response_class=FileResponse)
def download_preprocessed(request: Request, job_id: str) -> FileResponse:
    path = request.app.state.preprocessing_service.preprocessed_path(job_id)
    return FileResponse(
        path, filename="dataset_preprocessed.xlsx", media_type=XLSX_MEDIA_TYPE
    )
