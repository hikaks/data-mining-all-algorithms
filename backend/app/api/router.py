from fastapi import APIRouter
from app.api.routes.experiments import router as experiments_router

from app.api.routes.cleaning import router as cleaning_router
from app.api.routes.dataset import router as dataset_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.labeling import router as labeling_router
from app.api.routes.preprocessing import router as preprocessing_router
from app.api.routes.prediction import router as prediction_router
from app.api.routes.splitting import router as splitting_router
from app.api.routes.training import router as training_router


api_router = APIRouter()
api_router.include_router(experiments_router)
api_router.include_router(dataset_router)
api_router.include_router(cleaning_router)
api_router.include_router(labeling_router)
api_router.include_router(preprocessing_router)
api_router.include_router(splitting_router)
api_router.include_router(training_router)
api_router.include_router(evaluation_router)
api_router.include_router(prediction_router)
