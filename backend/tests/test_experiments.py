from dataclasses import replace
from hashlib import sha256
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import get_settings
from app.services.generic_pipeline import coerce_frame
from app.services.classifiers import StringClassifier, LEGACY_PARAMETERS, PARAMETERS
from app.core.exceptions import InvalidDatasetError
from tests.test_generic import generic_job, generic_content
from tests.test_dataset import upload, workbook_bytes
from tests.test_splitting import _split_ready_job
from tests.test_prediction import VALID_INPUT

ALGORITHMS = ['random_forest', 'decision_tree', 'svm_linear', 'knn']
VALUES = {'amount': None, 'segment': 'NEVER_SEEN', 'description': 'new input text', 'day': '2040-01-01'}


def ready(client, classes=('01', '1')):
    jid = generic_job(client, classes=classes)
    for stage in ('clean', 'preprocess'):
        response = client.post(f'/api/jobs/{jid}/{stage}')
        assert response.status_code == 200, response.text
    return jid


def create(client, jid, ratio=0.2, algorithm='random_forest'):
    response = client.post(f'/api/jobs/{jid}/experiments', json={'test_ratio': ratio, 'algorithm': algorithm})
    assert response.status_code == 201, response.text
    return response.json()['data']['experiment_id']


def run(client, jid, eid, stage):
    response = client.post(f'/api/jobs/{jid}/experiments/{eid}/{stage}')
    assert response.status_code == 200, response.text
    return response.json()['data']


def hashes(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('profile', ['binary', 'multiclass', 'maxkomp'])
@pytest.mark.parametrize('ratio', [0.2, 0.25, 0.3])
@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_experiment_end_to_end(client, tmp_path, profile, ratio, algorithm):
    jid = _split_ready_job(client) if profile == 'maxkomp' else ready(client, ('01', '1') if profile == 'binary' else ('A', 'B', 'C'))
    root = tmp_path / 'storage' / 'jobs' / jid
    original = hashes(root)
    eid = create(client, jid, ratio, algorithm)
    base = f'/api/jobs/{jid}/experiments/{eid}'
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': eid}).status_code == 409
    split = run(client, jid, eid, 'split')
    assert split['group_overlap_count'] == split['record_overlap_count'] == 0
    assert all(n >= 2 for n in split['train_distribution'].values())
    assert all(n >= 2 for n in split['test_distribution'].values())
    assert run(client, jid, eid, 'split') == split
    manifest = client.get(base + '/split-manifest').json()['data']
    assert manifest['configuration']['requested_test_ratio'] == ratio
    trained = run(client, jid, eid, 'train')
    descriptor = client.get(base).json()['data']
    metadata = client.get(base + '/model-metadata').json()['data']
    assert descriptor['parameter_version'] == metadata['configuration']['parameter_version'] == 2
    assert descriptor['parameters'] == metadata['configuration']['parameters'] == PARAMETERS[algorithm]
    if algorithm == 'svm_linear':
        solver = metadata['verification']['svm_solver']
        assert solver['converged'] is True and solver['fit_status'] == 0 and solver['max_iter'] == -1
        assert all(iterations > 0 for iterations in solver['iterations'])
    assert run(client, jid, eid, 'train') == trained
    evaluated = run(client, jid, eid, 'evaluate')
    assert run(client, jid, eid, 'evaluate') == evaluated
    evaluation = client.get(base + '/evaluation').json()['data']
    assert len(evaluation['confusion_matrix']['label_order']) == (3 if profile == 'multiclass' else 2)
    assert sum(evaluation['evaluation_scope']['actual_distribution'].values()) == split['test_rows']
    assert set(evaluation['evaluation_scope']['actual_distribution']) == set(evaluation['confusion_matrix']['label_order'])
    if profile == 'maxkomp':
        assert str(evaluation['metrics']['per_class']['TINDAK_LANJUT']['support']) in evaluation['limitations'][1]
    assert evaluation['feature_importance']['available'] is (algorithm in ('random_forest', 'decision_tree'))
    if algorithm == 'decision_tree':
        importance = client.get(base + '/feature-importance').json()['data']
        assert all(item['tree_std'] is None for item in importance['features'])
    for artifact in ('model', 'model-metadata', 'evaluation', 'split-manifest', 'feature-importance'):
        assert client.get(base + '/download/' + artifact).status_code == 200
    overview = client.get(f'/api/jobs/{jid}').json()['data']
    assert overview['status'] == 'EVALUATED' and overview['prediction_ready'] is False
    assert client.get(f'/api/jobs/{jid}/prediction/schema').status_code == 409
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': eid}).status_code == 200
    assert client.get(f'/api/jobs/{jid}/model-metadata').json()['data']['model_id'] == trained['model_id']
    assert client.get(f'/api/jobs/{jid}/evaluation').json()['data']['evaluation_id'] == evaluated['evaluation_id']
    result = client.post(f'/api/jobs/{jid}/predict', json=VALID_INPUT if profile == 'maxkomp' else {'features': VALUES})
    assert result.status_code == 200, result.text
    prediction = result.json()['data']
    assert prediction['experiment_id'] == eid
    assert prediction['confidence'] == prediction['probabilities'][prediction['prediction']]
    assert sum(prediction['probabilities'].values()) == pytest.approx(1, abs=1e-6)
    current = hashes(root)
    assert all(current[path] == digest for path, digest in original.items())
    # Another process loads artifacts/history rather than training or migrating.
    before = hashes(root)
    with TestClient(create_app(replace(get_settings(), storage_root=tmp_path / 'storage'))) as fresh:
        assert fresh.get(f'/api/jobs/{jid}/prediction/schema').status_code == 200
        assert fresh.get(f'/api/jobs/{jid}/predictions').json()['data']['items'][0]['experiment_id'] == eid
        assert fresh.get(base + '/evaluation').status_code == 200
    assert hashes(root) == before
    if profile != 'maxkomp':
        model = joblib.load(root / 'experiments' / eid / 'model' / 'model_pipeline.joblib')
        cfg = json.loads((root / 'config' / 'dataset_config.json').read_text())
        frame = coerce_frame(pd.read_excel(root / 'preprocessed' / 'dataset_preprocessed.xlsx', dtype=object, keep_default_na=False), cfg)
        train = frame.set_index('record_id').loc[manifest['train']['record_ids']]
        for name, transformer, columns in model.named_steps['preprocessor'].transformers_:
            if name.startswith(('numeric_', 'date_')):
                imputer = transformer.named_steps['imputer'] if algorithm in ('svm_linear', 'knn') else transformer
                assert imputer.statistics_ == pytest.approx(train[columns].astype(float).median().to_numpy())
                if algorithm in ('svm_linear', 'knn'):
                    scaler = transformer.named_steps['scaler']
                    assert scaler.mean_ == pytest.approx(imputer.transform(train[columns]).mean(axis=0))


def test_shared_split_manual_activation_and_origin_history(client, tmp_path):
    jid = ready(client)
    root = tmp_path / 'storage' / 'jobs' / jid
    first = create(client, jid)
    for stage in ('split', 'train', 'evaluate'):
        run(client, jid, first, stage)
    client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': first})
    prediction = client.post(f'/api/jobs/{jid}/predict', json={'features': VALUES}).json()['data']
    history_path = root / 'predictions' / 'predictions.jsonl'
    before_history = history_path.read_bytes()
    second = create(client, jid, algorithm='knn')
    for stage in ('split', 'train', 'evaluate'):
        run(client, jid, second, stage)
    assert history_path.read_bytes() == before_history
    items = client.get(f'/api/jobs/{jid}/experiments').json()['data']
    assert items['active_experiment_id'] == first
    details = {item['experiment_id']: item for item in items['items']}
    assert details[first]['split_reference'] == details[second]['split_reference']
    assert details[first]['test_set_id'] == details[second]['test_set_id']
    assert len(list((root / 'experiments' / 'splits').glob('*/split_manifest.json'))) == 1
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': second}).status_code == 200
    url = f"/api/jobs/{jid}/predictions/{prediction['prediction_id']}/actual-decision"
    assert client.patch(url, json={'actual_decision': '01'}).status_code == 200
    assert client.patch(url, json={'actual_decision': '1'}).status_code == 422
    assert client.patch(url, json={'actual_decision': '1', 'reason': 'Independent correction'}).status_code == 200
    assert history_path.read_bytes().startswith(before_history)
    assert client.get(f'/api/jobs/{jid}/predictions').json()['data']['items'][0]['model_id'] == prediction['model_id']
    third = create(client, jid, 0.3, 'decision_tree')
    run(client, jid, third, 'split')
    assert client.get(f'/api/jobs/{jid}/experiments/{third}').json()['data']['test_set_id'] != details[first]['test_set_id']


def test_legacy_adapter_reuses_manifest_without_mutation(client, tmp_path):
    jid = ready(client)
    for stage in ('split', 'train', 'evaluate'):
        assert client.post(f'/api/jobs/{jid}/{stage}').status_code == 200
    root = tmp_path / 'storage' / 'jobs' / jid
    before = hashes(root)
    assert client.get(f'/api/jobs/{jid}/experiments').json()['data']['active_experiment_id'] == 'legacy'
    assert hashes(root) == before
    eid = create(client, jid, algorithm='decision_tree')
    for stage in ('split', 'train', 'evaluate'):
        run(client, jid, eid, stage)
    assert client.get(f'/api/jobs/{jid}/experiments/{eid}').json()['data']['split_reference'] == 'legacy'
    assert client.get(f'/api/jobs/{jid}/experiments').json()['data']['active_experiment_id'] == 'legacy'
    assert all(hashes(root)[p] == h for p, h in before.items())


@pytest.mark.parametrize('payload', [{'test_ratio': 0.4}, {'algorithm': 'invalid'}, {'algorithm': 'knn', 'seed': 1}])
def test_invalid_request_creates_nothing(client, tmp_path, payload):
    jid = ready(client)
    root = tmp_path / 'storage' / 'jobs' / jid
    before = hashes(root)
    assert client.post(f'/api/jobs/{jid}/experiments', json=payload).status_code == 422
    assert hashes(root) == before and not (root / 'experiments').exists()


def test_source_config_and_model_checksum_errors(client, tmp_path):
    jid = ready(client)
    eid = create(client, jid)
    root = tmp_path / 'storage' / 'jobs' / jid
    base = f'/api/jobs/{jid}/experiments/{eid}'
    assert client.post(base + '/train').status_code == 409
    assert client.post(base + '/evaluate').status_code == 409
    cfg_path = root / 'config' / 'dataset_config.json'
    original = cfg_path.read_bytes()
    cfg = json.loads(original); cfg['revision'] += 1; cfg_path.write_text(json.dumps(cfg))
    assert client.post(base + '/split').status_code == 422
    cfg_path.write_bytes(original)
    source = root / 'preprocessed' / 'dataset_preprocessed.xlsx'
    source_original = source.read_bytes()
    source.write_bytes(source_original + b'changed')
    assert client.post(base + '/split').status_code == 422
    assert client.post(f'/api/jobs/{jid}/experiments', json={}).status_code == 422
    source.write_bytes(source_original)
    for stage in ('split', 'train', 'evaluate'):
        run(client, jid, eid, stage)
    descriptor_path = root / 'experiments' / eid / 'experiment.json'
    descriptor_original = descriptor_path.read_bytes()
    descriptor = json.loads(descriptor_original); descriptor['test_ratio'] = 0.3
    descriptor_path.write_text(json.dumps(descriptor))
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': eid}).status_code == 422
    descriptor_path.write_bytes(descriptor_original)
    model_path = root / 'experiments' / eid / 'model' / 'model_pipeline.joblib'
    model_path.write_bytes(model_path.read_bytes() + b'tampered')
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': eid}).status_code == 422
    assert client.get(base + '/evaluation').status_code == 422


def test_classifier_failures_publish_no_model(client, tmp_path, monkeypatch):
    jid = ready(client)
    eid = create(client, jid, algorithm='svm_linear')
    run(client, jid, eid, 'split')
    def fail(self, X, y):
        raise InvalidDatasetError('SVM belum konvergen')
    monkeypatch.setattr(StringClassifier, 'fit', fail)
    response = client.post(f'/api/jobs/{jid}/experiments/{eid}/train')
    assert response.status_code == 422
    detail = client.get(f'/api/jobs/{jid}/experiments/{eid}').json()['data']
    assert detail['status'] == 'SPLIT_READY' and detail['error']['stage'] == 'train'
    assert detail['operation'] is None and detail['model_id'] is None
    assert not (tmp_path / 'storage' / 'jobs' / jid / 'experiments' / eid / 'model' / 'model_pipeline.joblib').exists()
    monkeypatch.undo()
    with pytest.raises(InvalidDatasetError, match='lima'):
        StringClassifier('knn').fit(np.array([[0], [1], [2], [3]]), ['A', 'A', 'B', 'B'])


def test_insufficient_groups_keeps_created_state(client):
    rows = [[1, 'S', 'same text', '2030-01-01', 'A'], [1, 'S', 'same text', '2030-01-01', 'B']]
    jid = generic_job(client, rows=rows)
    client.post(f'/api/jobs/{jid}/clean'); client.post(f'/api/jobs/{jid}/preprocess')
    eid = create(client, jid)
    assert client.post(f'/api/jobs/{jid}/experiments/{eid}/split').status_code == 422
    detail = client.get(f'/api/jobs/{jid}/experiments/{eid}').json()['data']
    assert detail['status'] == 'CREATED' and detail['error']['stage'] == 'split'


def test_svm_predict_class_not_probability_argmax(client, monkeypatch):
    from app.services.prediction_service import PredictionService
    jid = ready(client)
    eid = create(client, jid, algorithm='svm_linear')
    for stage in ('split', 'train', 'evaluate'):
        run(client, jid, eid, stage)
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': eid}).status_code == 200
    original = PredictionService._load_verified_model
    class Scores:
        classes_ = np.array(['01', '1'])
        def predict(self, X): return np.array(['01'])
        def predict_proba(self, X): return np.array([[0.2, 0.8]])
    def scores(self, job_id):
        _, metadata, digest, evaluation = original(self, job_id)
        return Scores(), metadata, digest, evaluation
    monkeypatch.setattr(PredictionService, '_load_verified_model', scores)
    response = client.post(f'/api/jobs/{jid}/predict', json={'features': VALUES})
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['prediction'] == '01' and result['confidence'] == 0.2


def test_real_svm_convergence_guard(monkeypatch):
    from sklearn.svm import SVC
    original = SVC.fit
    def limited(self, X, y):
        original(self, X, y); self.fit_status_ = 1; return self
    monkeypatch.setattr(SVC, 'fit', limited)
    with pytest.raises(InvalidDatasetError, match='konvergen'):
        StringClassifier('svm_linear').fit(np.arange(20).reshape(-1, 1), ['A', 'B'] * 10)


def test_shared_split_tamper_not_adopted_by_retry(client, tmp_path):
    jid = ready(client)
    eid = create(client, jid)
    run(client, jid, eid, 'split')
    root = tmp_path / 'storage' / 'jobs' / jid
    split = next((root / 'experiments' / 'splits').glob('*/split_manifest.json'))
    split.write_bytes(split.read_bytes() + b' ')
    assert client.post(f'/api/jobs/{jid}/experiments/{eid}/split').status_code == 422
    assert client.post(f'/api/jobs/{jid}/experiments/{eid}/train').status_code == 422
    other = create(client, jid, algorithm='decision_tree')
    assert client.post(f'/api/jobs/{jid}/experiments/{other}/split').status_code == 422


def test_interrupted_operation_read_only_and_manual_retry(client, tmp_path):
    jid = ready(client)
    eid = create(client, jid)
    root = tmp_path / 'storage' / 'jobs' / jid
    path = root / 'experiments' / eid / 'experiment.json'
    descriptor = json.loads(path.read_bytes())
    descriptor['operation'] = 'split'
    path.write_text(json.dumps(descriptor))
    before = hashes(root)
    response = client.get(f'/api/jobs/{jid}/experiments/{eid}').json()['data']
    assert response['operation'] is None and response['error']['stage'] == 'split'
    assert hashes(root) == before
    run(client, jid, eid, 'split')
    overview = client.get(f'/api/jobs/{jid}').json()['data']
    assert overview['split_train_rows'] + overview['split_test_rows'] == 60


def test_unversioned_svm_uses_legacy_parameters_without_migration(client, tmp_path):
    jid = ready(client)
    eid = create(client, jid, algorithm='svm_linear')
    root = tmp_path / 'storage' / 'jobs' / jid
    path = root / 'experiments' / eid / 'experiment.json'
    descriptor = json.loads(path.read_bytes())
    del descriptor['parameter_version']
    descriptor['parameters'] = LEGACY_PARAMETERS['svm_linear']
    path.write_text(json.dumps(descriptor))
    for stage in ('split', 'train', 'evaluate'):
        run(client, jid, eid, stage)
    metadata = client.get(f'/api/jobs/{jid}/experiments/{eid}/model-metadata').json()['data']
    assert metadata['configuration']['parameter_version'] == 1
    assert metadata['verification']['svm_solver']['max_iter'] == 10000
    model = joblib.load(root / 'experiments' / eid / 'model' / 'model_pipeline.joblib')
    classifier = model.named_steps['classifier']
    assert classifier.estimator_.max_iter == 10000
    # Simulate loading the pre-versioned StringClassifier joblib class.
    del classifier.parameter_version
    model_path = root / 'experiments' / eid / 'model' / 'old_class.joblib'
    joblib.dump(model, model_path)
    restored = joblib.load(model_path).named_steps['classifier']
    assert restored.parameter_version == 1 and restored.get_params()['parameter_version'] == 1
    assert client.put(f'/api/jobs/{jid}/active-experiment', json={'experiment_id': eid}).status_code == 200
    before = hashes(root)
    assert client.get(f'/api/jobs/{jid}/experiments').status_code == 200
    assert client.get(f'/api/jobs/{jid}/prediction/schema').status_code == 200
    run(client, jid, eid, 'train')
    run(client, jid, eid, 'evaluate')
    assert hashes(root) == before
    replacement = create(client, jid, algorithm='svm_linear')
    run(client, jid, replacement, 'split')
    details = client.get(f'/api/jobs/{jid}/experiments/{replacement}').json()['data']
    assert details['parameters']['max_iter'] == -1
    assert details['test_set_id'] == client.get(f'/api/jobs/{jid}/experiments/{eid}').json()['data']['test_set_id']
    assert client.get(f'/api/jobs/{jid}/experiments').json()['data']['active_experiment_id'] == eid


@pytest.mark.parametrize('version', [0, 3, '2', True])
def test_invalid_parameter_version_rejected_without_training(client, tmp_path, version):
    jid = ready(client)
    eid = create(client, jid, algorithm='svm_linear')
    root = tmp_path / 'storage' / 'jobs' / jid
    path = root / 'experiments' / eid / 'experiment.json'
    descriptor = json.loads(path.read_bytes())
    descriptor['parameter_version'] = version
    path.write_text(json.dumps(descriptor))
    before = hashes(root)
    assert client.post(f'/api/jobs/{jid}/experiments/{eid}/split').status_code == 422
    assert hashes(root) == before
