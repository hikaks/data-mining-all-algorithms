from datetime import datetime, timezone
import secrets

from app.core.config import Settings
from app.core.exceptions import InvalidDatasetError, InvalidJobStateError, ArtifactNotFoundError
from app.services.dataset_configuration import DatasetConfigurationService, CONFIGURATION_LOCK
from app.services.classifiers import PARAMETERS, PARAMETER_VERSION, parameters_for
from app.services.split_service import SplitService
from app.services.training_service import TrainingService
from app.services.evaluation_service import EvaluationService
from app.storage.job_manager import JobManager
from app.storage.file_manager import read_json, write_json_atomic
from app.storage.experiments import ExperimentJobs, experiment_path, artifact_jobs, active_id
from app.utils.tabular import object_hash


RUNNING_OPERATIONS = set()


class ExperimentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs = JobManager(settings.storage_root)
        self.configuration = DatasetConfigurationService(settings)

    def _source(self, job_id):
        source = self.jobs.require_job_path(job_id) / 'preprocessed' / 'dataset_preprocessed.xlsx'
        if not source.is_file():
            raise InvalidJobStateError('Selesaikan preprocessing sebelum membuat eksperimen.')
        return source

    def create(self, job_id, request):
        with CONFIGURATION_LOCK:
            source = self._source(job_id)
            config = self.configuration.get(job_id)
            report = read_json(self.jobs.report_path(job_id, 'preprocessing_report.json'))
            source_hash = SplitService._sha256(source)
            if source_hash != report['artifact_integrity']['output_preprocessed_sha256']:
                raise InvalidDatasetError('Checksum dataset preprocessing berubah.')
            if not config.get('legacy') and object_hash(config) != report['artifact_integrity'].get('dataset_configuration_sha256'):
                raise InvalidDatasetError('Checksum konfigurasi preprocessing berubah.')
            identity = dict(source_sha256=source_hash, configuration_sha256=object_hash(config),
                            test_ratio=request.test_ratio, random_state=42)
            reference = object_hash(identity)
            legacy = self.jobs.report_path(job_id, 'split_manifest.json')
            if legacy.is_file():
                manifest = read_json(legacy)
                cfg = manifest['configuration']
                snapshot = cfg.get('dataset_configuration_sha256')
                if (manifest['source_artifact']['sha256'] == source_hash
                        and cfg['requested_test_ratio'] == request.test_ratio and cfg['random_state'] == 42
                        and (snapshot == object_hash(config) or (config.get('legacy') and snapshot is None))):
                    reference = 'legacy'
            experiment_id = 'EXP-' + secrets.token_hex(8).upper()
            root = self.jobs.require_job_path(job_id) / 'experiments' / experiment_id
            (root / 'model').mkdir(parents=True)
            (root / 'reports').mkdir()
            experiment = dict(job_id=job_id, experiment_id=experiment_id, created_at=self._now(),
                status='CREATED', algorithm=request.algorithm, parameter_version=PARAMETER_VERSION,
                parameters=parameters_for(request.algorithm),
                test_ratio=request.test_ratio, random_state=42, dataset_configuration=config,
                dataset_configuration_sha256=object_hash(config), source_sha256=source_hash,
                split_reference=reference, operation=None, error=None, progress={})
            write_json_atomic(root / 'experiment.json', experiment)
            return self.detail(job_id, experiment_id)

    def _verify(self, job_id, experiment):
        config = self.configuration.get(job_id)
        if object_hash(config) != experiment['dataset_configuration_sha256']:
            raise InvalidDatasetError('Checksum konfigurasi eksperimen berubah.')
        if object_hash(experiment['dataset_configuration']) != object_hash(config) or experiment['random_state'] != 42:
            raise InvalidDatasetError('Snapshot konfigurasi eksperimen berubah.')
        if SplitService._sha256(self._source(job_id)) != experiment['source_sha256']:
            raise InvalidDatasetError('Checksum sumber eksperimen berubah.')
        identity = dict(source_sha256=experiment['source_sha256'], configuration_sha256=object_hash(config),
                        test_ratio=experiment['test_ratio'], random_state=42)
        if experiment['split_reference'] not in ('legacy', object_hash(identity)):
            raise InvalidDatasetError('Referensi split eksperimen berubah.')
        if experiment['parameters'] != parameters_for(experiment['algorithm'], experiment.get('parameter_version', 1)):
            raise InvalidDatasetError('Parameter eksperimen berubah.')

    def services(self, job_id, experiment_id=None):
        jobs = artifact_jobs(self.settings.storage_root, job_id, experiment_id)
        services = {'split': SplitService(self.settings), 'train': TrainingService(self.settings),
                    'evaluate': EvaluationService(self.settings)}
        for service in services.values():
            service.jobs = jobs
        return services

    def run(self, job_id, experiment_id, stage):
        with CONFIGURATION_LOCK:
            if experiment_id == 'legacy':
                services = self.services(job_id, 'legacy')
                return {'split': services['split'].create_split, 'train': services['train'].train,
                        'evaluate': services['evaluate'].evaluate}[stage](job_id)
            root = experiment_path(self.jobs, job_id, experiment_id)
            path = root / 'experiment.json'
            experiment = read_json(path)
            self._verify(job_id, experiment)
            jobs = ExperimentJobs(self.settings.storage_root, job_id, experiment_id)
            manifest_path = jobs.report_path(job_id, 'split_manifest.json')
            if manifest_path.is_file():
                known_hashes = []
                if experiment['split_reference'] == 'legacy':
                    known_hashes.append(self.jobs.read_metadata(job_id).get('split_manifest_sha256'))
                directory = self.jobs.require_job_path(job_id) / 'experiments'
                for descriptor in directory.glob('EXP-*/experiment.json'):
                    peer = read_json(descriptor)
                    if peer['split_reference'] == experiment['split_reference']:
                        known_hashes.append(peer.get('split_sha256'))
                current_hash = SplitService._sha256(manifest_path)
                if any(digest and digest != current_hash for digest in known_hashes):
                    raise InvalidDatasetError('Checksum manifest split bersama berubah.')
            if stage == 'split' and manifest_path.is_file() and experiment.get('split_sha256'):
                if experiment['split_sha256'] != SplitService._sha256(manifest_path):
                    raise InvalidDatasetError('Checksum split eksperimen berubah.')
            if stage != 'split' and not manifest_path.is_file():
                raise InvalidJobStateError('Buat split eksperimen terlebih dahulu.')
            if stage in ('train', 'evaluate'):
                manifest = read_json(manifest_path)
                if (manifest['source_artifact']['sha256'] != experiment['source_sha256']
                        or manifest['configuration']['requested_test_ratio'] != experiment['test_ratio']):
                    raise InvalidDatasetError('Split tidak cocok dengan eksperimen.')
                if experiment.get('split_sha256') != SplitService._sha256(manifest_path):
                    raise InvalidDatasetError('Checksum split eksperimen berubah.')
            if stage == 'evaluate' and experiment['status'] not in ('TRAINED', 'EVALUATED'):
                raise InvalidJobStateError('Latih model eksperimen terlebih dahulu.')
            experiment.update(operation=stage, error=None)
            operation_key = (job_id, experiment_id)
            RUNNING_OPERATIONS.add(operation_key)
            write_json_atomic(path, experiment)
            try:
                services = self.services(job_id, experiment_id)
                if stage == 'split':
                    if not manifest_path.is_file():
                        manifest_path.parent.mkdir(parents=True, exist_ok=True)
                    result = services['split'].create_split(job_id, experiment['test_ratio'])
                    manifest = read_json(manifest_path)
                    frame = SplitService._read_preprocessed(self._source(job_id))
                    TrainingService._select_manifest_rows(job_id, frame, manifest, experiment['source_sha256'])
                elif stage == 'train':
                    result = services['train'].train(job_id, experiment['algorithm'], experiment_id,
                                                     experiment.get('parameter_version', 1))
                else:
                    result = services['evaluate'].evaluate(job_id)
                experiment = read_json(path)
                if stage == 'split':
                    if experiment['status'] == 'CREATED':
                        experiment['status'] = 'SPLIT_READY'
                    experiment['split_sha256'] = SplitService._sha256(manifest_path)
                experiment.update(operation=None, error=None)
                write_json_atomic(path, experiment)
                return result
            except Exception as error:
                experiment = read_json(path)
                experiment.update(operation=None, error={'stage': stage, 'message': str(error)})
                write_json_atomic(path, experiment)
                raise
            finally:
                RUNNING_OPERATIONS.discard(operation_key)

    def detail(self, job_id, experiment_id):
        root = self.jobs.require_job_path(job_id)
        if experiment_id == 'legacy':
            manifest_path = self.jobs.report_path(job_id, 'split_manifest.json')
            if not manifest_path.is_file():
                raise ArtifactNotFoundError('Model sebelumnya')
            experiment = dict(job_id=job_id, experiment_id='legacy', label='Model sebelumnya',
                created_at=self.jobs.read_metadata(job_id)['created_at'], algorithm='random_forest',
                status='SPLIT_READY', operation=None, error=None, parameters=PARAMETERS['random_forest'])
            jobs = self.jobs
        else:
            experiment = read_json(experiment_path(self.jobs, job_id, experiment_id) / 'experiment.json')
            jobs = ExperimentJobs(self.settings.storage_root, job_id, experiment_id)
        experiment = dict(experiment)
        if experiment.get('operation') and (job_id, experiment_id) not in RUNNING_OPERATIONS:
            # A previous process stopped mid-request. GET remains read-only; an
            # explicit retry checks artifacts before resuming the same operation.
            experiment['error'] = {'stage': experiment['operation'],
                'message': 'Operasi sebelumnya terputus. Baca status lalu jalankan kembali secara manual.'}
            experiment['operation'] = None
        experiment['active'] = active_id(self.jobs, job_id) == experiment_id
        experiment['model_id'] = None
        experiment['metrics'] = None
        experiment['training_seconds'] = None
        manifest = jobs.report_path(job_id, 'split_manifest.json')
        if manifest.is_file():
            split = read_json(manifest)
            if experiment_id == 'legacy':
                experiment['test_ratio'] = split['configuration']['requested_test_ratio']
            experiment.update(actual_test_ratio=split['selection']['actual_test_ratio'],
                test_set_id=split['source_artifact']['sha256'] + ':' + object_hash(split['test']['record_ids']))
        model_metadata = jobs.model_metadata_path(job_id)
        if model_metadata.is_file():
            metadata = read_json(model_metadata)
            experiment.update(model_id=metadata['model_id'], training_seconds=metadata['verification']['training_seconds'])
            if experiment_id == 'legacy':
                experiment['status'] = 'TRAINED'
        evaluation = jobs.report_path(job_id, 'evaluation.json')
        if evaluation.is_file():
            experiment['metrics'] = read_json(evaluation)['metrics']
            if experiment_id == 'legacy':
                experiment['status'] = 'EVALUATED'
        return experiment

    def list(self, job_id):
        with CONFIGURATION_LOCK:
            root = self.jobs.require_job_path(job_id)
            items = []
            if self.jobs.report_path(job_id, 'split_manifest.json').is_file():
                items.append(self.detail(job_id, 'legacy'))
            directory = root / 'experiments'
            if directory.is_dir():
                items.extend(self.detail(job_id, p.name) for p in directory.glob('EXP-*') if p.is_dir())
            items.sort(key=lambda x: (x['created_at'], x['experiment_id']), reverse=True)
            return {'items': items, 'active_experiment_id': active_id(self.jobs, job_id)}

    def activate(self, job_id, experiment_id):
        with CONFIGURATION_LOCK:
            experiment = self.detail(job_id, experiment_id)
            if experiment['status'] != 'EVALUATED':
                raise InvalidJobStateError('Evaluasi eksperimen sebelum mengaktifkan model.')
            if experiment_id != 'legacy':
                self._verify(job_id, experiment)
            services = self.services(job_id, experiment_id)
            services['evaluate'].report(job_id)
            metadata = services['train'].metadata(job_id)
            if experiment_id != 'legacy' and (metadata.configuration.get('experiment_id') != experiment_id
                    or metadata.configuration.get('algorithm_id') != experiment['algorithm']
                    or metadata.configuration['parameters'] != experiment['parameters']
                    or metadata.configuration.get('parameter_version', 1) != experiment.get('parameter_version', 1)):
                raise InvalidDatasetError('Metadata model tidak cocok dengan eksperimen.')
            path = self.jobs.require_job_path(job_id) / 'experiments' / 'active.json'
            path.parent.mkdir(exist_ok=True)
            write_json_atomic(path, {'experiment_id': experiment_id, 'activated_at': self._now()})
            return self.detail(job_id, experiment_id)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()
