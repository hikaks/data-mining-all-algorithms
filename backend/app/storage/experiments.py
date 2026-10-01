"""Read-only legacy adapter and artifact scopes; never rewrite historical jobs."""
from pathlib import Path
import re

from app.core.exceptions import AppError, InvalidDatasetError
from app.storage.job_manager import JobManager
from app.storage.file_manager import read_json, write_json_atomic

EXPERIMENT_PATTERN = re.compile(r'^EXP-[A-F0-9]{16}$')
SCOPED_REPORTS = {'split_manifest.json', 'evaluation.json', 'feature_importance.json'}


def experiment_path(jobs, job_id, experiment_id):
    if not EXPERIMENT_PATTERN.fullmatch(experiment_id):
        raise AppError('EXPERIMENT_NOT_FOUND', 'Eksperimen tidak ditemukan.', 404)
    path = jobs.require_job_path(job_id) / 'experiments' / experiment_id
    if not (path / 'experiment.json').is_file():
        raise AppError('EXPERIMENT_NOT_FOUND', 'Eksperimen tidak ditemukan.', 404)
    return path


def active_id(jobs, job_id):
    root = jobs.require_job_path(job_id)
    pointer = root / 'experiments' / 'active.json'
    if pointer.is_file():
        value = read_json(pointer)['experiment_id']
        if value != 'legacy':
            experiment_path(jobs, job_id, value)
        return value
    if (root / 'reports' / 'evaluation.json').is_file():
        return 'legacy'
    return None


class ExperimentJobs(JobManager):
    def __init__(self, root, job_id, experiment_id):
        super().__init__(root)
        self.original = JobManager(root)
        self.job_id = job_id
        self.experiment_id = experiment_id
        self.scope = experiment_path(self.original, job_id, experiment_id)

    def read_metadata(self, job_id):
        metadata = self.original.read_metadata(job_id)
        experiment = read_json(self.scope / 'experiment.json')
        metadata.update(experiment.get('progress', {}))
        state = experiment['status']
        metadata['status'] = state if state in ('TRAINED', 'EVALUATED') else 'PREPROCESSED'
        return metadata

    def update_metadata(self, job_id, updates):
        path = self.scope / 'experiment.json'
        experiment = read_json(path)
        experiment.setdefault('progress', {}).update(updates)
        if updates.get('status') in ('TRAINED', 'EVALUATED'):
            experiment['status'] = updates['status']
        write_json_atomic(path, experiment)
        return self.read_metadata(job_id)

    def preprocessed_dataset_path(self, job_id):
        return self.original.require_job_path(job_id) / 'preprocessed' / 'dataset_preprocessed.xlsx'

    def model_pipeline_path(self, job_id):
        return self.scope / 'model' / 'model_pipeline.joblib'

    def model_metadata_path(self, job_id):
        return self.scope / 'model' / 'model_metadata.json'

    def report_path(self, job_id, filename):
        if filename == 'split_manifest.json':
            reference = read_json(self.scope / 'experiment.json')['split_reference']
            if reference == 'legacy':
                return self.original.report_path(job_id, filename)
            if not re.fullmatch(r'[a-f0-9]{64}', reference):
                raise InvalidDatasetError('Referensi split tidak valid.')
            return self.original.require_job_path(job_id) / 'experiments' / 'splits' / reference / filename
        if filename in SCOPED_REPORTS:
            return self.scope / 'reports' / filename
        return self.original.report_path(job_id, filename)


def artifact_jobs(root, job_id, experiment_id=None):
    jobs = JobManager(root)
    selected = active_id(jobs, job_id) if experiment_id is None else experiment_id
    return jobs if selected in (None, 'legacy') else ExperimentJobs(root, job_id, selected)


def metadata_for_model(root, job_id, model_id):
    jobs = JobManager(root)
    original = jobs.model_metadata_path(job_id)
    candidates = [original]
    directory = jobs.require_job_path(job_id) / 'experiments'
    if directory.is_dir():
        candidates.extend(directory.glob('EXP-*/model/model_metadata.json'))
    for path in candidates:
        if path.is_file():
            metadata = read_json(path)
            if metadata.get('model_id') == model_id:
                return metadata
    raise InvalidDatasetError('Model asal riwayat tidak ditemukan.')
