from typing import Literal
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from app.schemas.common import SuccessResponse

router = APIRouter(tags=['Model Experiments'])


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    test_ratio: Literal[0.2, 0.25, 0.3] = 0.2
    algorithm: Literal['random_forest', 'decision_tree', 'svm_linear', 'knn'] = 'random_forest'


class ActiveExperimentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    experiment_id: str


@router.get('/jobs/{job_id}/experiments')
def list_experiments(request: Request, job_id: str):
    return SuccessResponse(data=request.app.state.experiment_service.list(job_id), message='Eksperimen dimuat.')


@router.post('/jobs/{job_id}/experiments', status_code=201)
def create_experiment(request: Request, job_id: str, payload: ExperimentRequest):
    return SuccessResponse(data=request.app.state.experiment_service.create(job_id, payload), message='Eksperimen dibuat.')


@router.put('/jobs/{job_id}/active-experiment')
def activate_experiment(request: Request, job_id: str, payload: ActiveExperimentRequest):
    return SuccessResponse(data=request.app.state.experiment_service.activate(job_id, payload.experiment_id), message='Model aktif diperbarui.')


@router.get('/jobs/{job_id}/experiments/{experiment_id}')
def experiment_detail(request: Request, job_id: str, experiment_id: str):
    return SuccessResponse(data=request.app.state.experiment_service.detail(job_id, experiment_id), message='Detail eksperimen dimuat.')


@router.post('/jobs/{job_id}/experiments/{experiment_id}/{stage}')
def run_experiment(request: Request, job_id: str, experiment_id: str, stage: Literal['split', 'train', 'evaluate']):
    return SuccessResponse(data=request.app.state.experiment_service.run(job_id, experiment_id, stage), message='Tahap eksperimen berhasil.')


REPORT_METHODS = {'split-manifest': ('split', 'manifest'), 'model-metadata': ('train', 'metadata'),
                  'evaluation': ('evaluate', 'report'), 'feature-importance': ('evaluate', 'feature_importance')}
DOWNLOAD_METHODS = {'split-manifest': ('split', 'manifest_path'), 'model': ('train', 'model_path'),
                    'model-metadata': ('train', 'metadata'),
                    'evaluation': ('evaluate', 'evaluation_path'), 'feature-importance': ('evaluate', 'feature_importance_path')}


@router.get('/jobs/{job_id}/experiments/{experiment_id}/download/{artifact}')
def download_experiment(request: Request, job_id: str, experiment_id: str, artifact: Literal['split-manifest', 'model', 'model-metadata', 'evaluation', 'feature-importance']):
    services = request.app.state.experiment_service.services(job_id, experiment_id)
    name, method = DOWNLOAD_METHODS[artifact]
    path = getattr(services[name], method)(job_id)
    if artifact == 'model-metadata':
        path = services['train'].jobs.model_metadata_path(job_id)
    return FileResponse(path, filename=path.name, media_type='application/octet-stream' if artifact == 'model' else 'application/json')


@router.get('/jobs/{job_id}/experiments/{experiment_id}/{report}')
def read_experiment(request: Request, job_id: str, experiment_id: str, report: Literal['split-manifest', 'model-metadata', 'evaluation', 'feature-importance']):
    services = request.app.state.experiment_service.services(job_id, experiment_id)
    name, method = REPORT_METHODS[report]
    return SuccessResponse(data=getattr(services[name], method)(job_id), message='Laporan eksperimen dimuat.')
