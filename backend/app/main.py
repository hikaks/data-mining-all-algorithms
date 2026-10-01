from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.services.cleaning_service import CleaningService
from app.services.dataset_service import DatasetService
from app.services.dataset_configuration import DatasetConfigurationService
from app.services.evaluation_service import EvaluationService
from app.services.labeling_service import LabelingService
from app.services.preprocessing_service import PreprocessingService
from app.services.prediction_service import PredictionService
from app.services.split_service import SplitService
from app.services.training_service import TrainingService
from app.services.experiment_service import ExperimentService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings.storage_root.mkdir(parents=True, exist_ok=True)
        application.state.dataset_service = DatasetService(active_settings)
        application.state.dataset_configuration = DatasetConfigurationService(active_settings)
        application.state.cleaning_service = CleaningService(active_settings)
        application.state.labeling_service = LabelingService(active_settings)
        application.state.preprocessing_service = PreprocessingService(active_settings)
        application.state.split_service = SplitService(active_settings)
        application.state.training_service = TrainingService(active_settings)
        application.state.evaluation_service = EvaluationService(active_settings)
        application.state.prediction_service = PredictionService(active_settings)
        application.state.experiment_service = ExperimentService(active_settings)
        yield

    application = FastAPI(
        title=active_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(AppError)
    async def app_error_handler(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "success": False,
                "error": {"code": error.code, "message": error.message},
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request tidak valid.",
                },
            },
        )

    @application.get("/health", tags=["System"])
    def health() -> dict[str, object]:
        return {
            "success": True,
            "data": {"status": "healthy"},
            "message": "Backend tersedia.",
        }

    application.include_router(api_router, prefix=active_settings.api_prefix)
    return application


app = create_app()
