from io import BytesIO
from hashlib import sha256
from dataclasses import replace
import json

import joblib
import pandas as pd
import pytest
from openpyxl import Workbook
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import get_settings
from app.services.generic_pipeline import coerce_frame, model_columns, prepare_features
from tests.test_dataset import upload, workbook_bytes


FEATURES = [{'name': 'amount', 'kind': 'numeric'}, {'name': 'segment', 'kind': 'categorical'}, {'name': 'description', 'kind': 'text'}, {'name': 'day', 'kind': 'date'}]


def generic_content(classes=('A', 'B', 'C'), separator=None, rows=None):
    values = rows if rows is not None else [[index if index % 7 else None, 'group' + str(index % 3), f'note sample token{index}', f'2030-02-{index % 28 + 1:02d}', classes[index % len(classes)]] for index in range(60)]
    frame = pd.DataFrame(values, columns=['amount', 'segment', 'description', 'day', 'result'])
    if separator:
        return ('\ufeff' + frame.to_csv(index=False, sep=separator)).encode('utf-8')
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame({'notes': ['not the dataset']}).to_excel(writer, sheet_name='Notes', index=False)
        frame.to_excel(writer, sheet_name='Free sheet', index=False)
    return buffer.getvalue()


def configure(client, job_id, **changes):
    payload = {'profile': 'generic', 'sheet_name': 'Free sheet', 'target_column': 'result', 'features': FEATURES, **changes}
    return client.put(f'/api/jobs/{job_id}/dataset/configuration', json=payload)


def generic_job(client, *, classes=('A', 'B', 'C'), separator=None, rows=None):
    content = generic_content(classes, separator, rows)
    response = upload(client, content, 'generic.csv' if separator else 'generic.xlsx', configure=False)
    assert response.status_code == 201, response.text
    job_id = response.json()['data']['job_id']
    saved = configure(client, job_id, sheet_name=None if separator else 'Free sheet', delimiter=separator)
    assert saved.status_code == 200, saved.text
    return job_id


@pytest.mark.parametrize('separator', [None, ';'])
def test_generic_cleaning_reports_preserve_column_mapping_and_artifacts(client, tmp_path, separator):
    job_id = generic_job(client, separator=separator)
    response = client.post(f'/api/jobs/{job_id}/clean')
    assert response.status_code == 200, response.text
    root = tmp_path / 'storage' / 'jobs' / job_id
    before = {str(path): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    for suffix in ('', '?include_details=false'):
        response = client.get(f'/api/jobs/{job_id}/cleaning-report{suffix}')
        assert response.status_code == 200, response.text
        assert response.headers['content-type'].startswith('application/json')
        report = response.json()['data']
        assert report['rows_after'] == 60
        assert isinstance(report['normalization']['operation_count'], int)
        assert report['normalization']['source_column_map'] == {
            name: name for name in ('amount', 'segment', 'description', 'day', 'result')
        }
        if suffix:
            for section in ('invalid_dates', 'incomplete_records', 'duplicate_records', 'operations', 'removed_empty_records', 'potential_duplicates'):
                assert report[section] == []
    assert client.get(f'/api/jobs/{job_id}').json()['data']['status'] == 'CLEANED'
    assert before == {str(path): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    response = client.post(f'/api/jobs/{job_id}/preprocess')
    assert response.status_code == 200, response.text


@pytest.mark.parametrize('classes,separator', [(('A', 'B'), None), (('A', 'B', 'C'), None), (('01', '02', '03'), ','), (('NA', 'OTHER'), ';'), (('NO', 'YES'), '\t'), (('01', '1'), ',')])
def test_generic_end_to_end_dynamic_model_history_and_reload(client, tmp_path, classes, separator):
    job_id = generic_job(client, classes=classes, separator=separator)
    root = tmp_path / 'storage' / 'jobs' / job_id
    raw = root / 'raw' / ('dataset.csv' if separator else 'dataset.xlsx')
    before = sha256(raw.read_bytes()).hexdigest()
    for stage in ('clean', 'preprocess', 'split', 'train', 'evaluate'):
        response = client.post(f'/api/jobs/{job_id}/{stage}')
        assert response.status_code == 200, f'{stage}: {response.text}'
    assert sha256(raw.read_bytes()).hexdigest() == before
    report = client.get(f'/api/jobs/{job_id}/evaluation').json()['data']
    assert set(report['confusion_matrix']['label_order']) == set(classes)
    assert len(report['confusion_matrix']['values']) == len(classes)
    assert report['metrics']['positive_class'] is None
    assert report['metrics']['highlighted_class'] in classes
    assert report['metrics']['macro_average']['f1'] >= 0
    assert report['metrics']['weighted_average']['f1'] >= 0
    schema = client.get(f'/api/jobs/{job_id}/prediction/schema').json()['data']
    assert schema['features'] == FEATURES
    assert set(schema['classes']) == set(classes)
    values = {'amount': None, 'segment': 'NEW_CATEGORY', 'description': 'unseen new text', 'day': '2040-01-01'}
    prediction = client.post(f'/api/jobs/{job_id}/predict', json={'features': values})
    assert prediction.status_code == 200, prediction.text
    result = prediction.json()['data']
    assert result['prediction'] in classes and set(result['probabilities']) == set(classes)
    url = f"/api/jobs/{job_id}/predictions/{result['prediction_id']}/actual-decision"
    assert client.patch(url, json={'actual_decision': classes[0]}).status_code == 200
    assert client.patch(url, json={'actual_decision': classes[1]}).status_code == 422
    assert client.patch(url, json={'actual_decision': classes[1], 'reason': 'Independent correction'}).status_code == 200
    history = client.get(f'/api/jobs/{job_id}/predictions').json()['data']
    assert history['event_count'] == 3
    assert history['items'][0]['input']['features']['segment'] == 'NEW_CATEGORY'
    assert client.patch(url, json={'actual_decision': 'NOT_A_CLASS'}).status_code == 422
    assert client.post(f'/api/jobs/{job_id}/predict', json={'features': {**values, 'result': classes[0]}}).status_code == 422
    assert configure(client, job_id).status_code == 409
    model = joblib.load(root / 'model' / 'model_pipeline.joblib')
    config = json.loads((root / 'config' / 'dataset_config.json').read_text())
    prepared, _ = prepare_features(values, config)
    assert model.predict(pd.DataFrame([prepared]))[0] == result['prediction']
    # A fresh application process must read artifacts/history, not rebuild them.
    files_before = {str(path): sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file()}
    with TestClient(create_app(replace(get_settings(), storage_root=tmp_path / 'storage'))) as fresh:
        assert fresh.get(f'/api/jobs/{job_id}/predictions').json()['data'] == history
        assert fresh.get(f'/api/jobs/{job_id}/prediction/schema').status_code == 200
    assert files_before == {str(path): sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file()}


def test_configuration_gate_validation_and_revision(client):
    job_id = upload(client, generic_content(), configure=False).json()['data']['job_id']
    for stage in ('clean', 'preprocess', 'split', 'train', 'evaluate'):
        assert client.post(f'/api/jobs/{job_id}/{stage}').status_code == 409
    assert client.get(f'/api/jobs/{job_id}/dataset/preview').status_code == 200
    assert client.get(f'/api/jobs/{job_id}').json()['data']['configuration_ready'] is False
    assert configure(client, job_id, features=[{'name': 'result', 'kind': 'categorical'}]).status_code == 422
    assert configure(client, job_id, features=[]).status_code == 422
    assert configure(client, job_id).status_code == 200
    assert configure(client, job_id, features=FEATURES[:2]).status_code == 200
    assert client.post(f'/api/jobs/{job_id}/clean').status_code == 200
    assert configure(client, job_id).status_code == 409


@pytest.mark.parametrize('headers', [('A', 'A'), ('A', None), ('A', ' A ')])
@pytest.mark.parametrize('format', ['xlsx', 'csv'])
def test_invalid_headers_rejected_before_pandas_mangling(client, headers, format):
    if format == 'csv':
        content = (','.join(value or '' for value in headers) + '\n1,2\n').encode()
    else:
        book = Workbook(); book.active.append(headers); book.active.append([1, 2]); buffer = BytesIO(); book.save(buffer); content = buffer.getvalue()
    assert upload(client, content, 'bad.' + format, configure=False).status_code == 422


@pytest.mark.parametrize('column,value,kind', [('amount', 'not numeric', 'numeric'), ('day', 'impossible date', 'date'), ('amount', 'inf', 'numeric')])
def test_wrong_type_reports_column_and_row(client, column, value, kind):
    rows = [[1, 'S', 'description', '2030-01-01', 'A'], [2, 'T', 'more text', '2030-01-02', 'B']]
    rows[1][[f['name'] for f in FEATURES].index(column)] = value
    job_id = upload(client, generic_content(rows=rows), configure=False).json()['data']['job_id']
    response = configure(client, job_id)
    assert response.status_code == 422
    assert column in response.json()['error']['message'] and 'baris 3' in response.json()['error']['message']


def test_empty_target_duplicates_conflicts_and_group_isolation(client, tmp_path):
    rows = [[index, 'S', f'sample {index}', '2030-01-01', 'A' if index % 2 else 'B'] for index in range(40)]
    rows += [rows[0], [*rows[0][:-1], 'A'], [100, 'S', 'missing target', '2030-01-01', None]]
    job_id = generic_job(client, rows=rows)
    assert client.post(f'/api/jobs/{job_id}/clean').json()['data']['duplicates_removed'] == 1
    result = client.post(f'/api/jobs/{job_id}/preprocess').json()['data']
    assert result['excluded_rows'] == 1 and result['label_conflict_groups'] == 1
    manifest = client.post(f'/api/jobs/{job_id}/split').json()['data']
    assert manifest['group_overlap_count'] == 0
    full = client.get(f'/api/jobs/{job_id}/split-manifest').json()['data']
    assert not set(full['train']['group_ids']) & set(full['test']['group_ids'])
    assert not set(full['train']['record_ids']) & set(full['test']['record_ids'])


def test_one_class_all_empty_feature_and_insufficient_groups(client):
    job_id = upload(client, generic_content(classes=('A',)), configure=False).json()['data']['job_id']
    assert configure(client, job_id).status_code == 422
    rows = [[None, 'S', 'text', '2030-01-01', label] for label in ('A', 'B')]
    job_id = upload(client, generic_content(rows=rows), configure=False).json()['data']['job_id']
    assert configure(client, job_id).status_code == 422
    rows = [[index, 'S', f'text {index}', '2030-01-01', label] for index, label in enumerate(('A', 'A', 'B', 'B'))]
    job_id = generic_job(client, rows=rows)
    for stage in ('clean', 'preprocess'):
        assert client.post(f'/api/jobs/{job_id}/{stage}').status_code == 200
    error = client.post(f'/api/jobs/{job_id}/split')
    assert error.status_code == 422 and error.json()['error']['message']


def test_checksum_configuration_change_detected(client, tmp_path):
    job_id = generic_job(client)
    for stage in ('clean', 'preprocess', 'split', 'train', 'evaluate'):
        assert client.post(f'/api/jobs/{job_id}/{stage}').status_code == 200
    path = tmp_path / 'storage' / 'jobs' / job_id / 'config' / 'dataset_config.json'
    config = json.loads(path.read_text()); config['features'][0]['kind'] = 'categorical'
    path.write_text(json.dumps(config))  # disposable test fixture tampering only
    assert client.get(f'/api/jobs/{job_id}/prediction/schema').status_code == 422
    assert client.get(f'/api/jobs/{job_id}/model-metadata').status_code == 422
    assert client.post(f'/api/jobs/{job_id}/train').status_code == 422


def test_learned_transforms_fit_only_manifest_train_rows(client, tmp_path):
    job_id = generic_job(client)
    for stage in ('clean', 'preprocess', 'split', 'train'):
        response = client.post(f'/api/jobs/{job_id}/{stage}')
        assert response.status_code == 200, response.text
    root = tmp_path / 'storage' / 'jobs' / job_id
    config = json.loads((root / 'config' / 'dataset_config.json').read_text())
    manifest = json.loads((root / 'reports' / 'split_manifest.json').read_text())
    prepared = coerce_frame(pd.read_excel(root / 'preprocessed' / 'dataset_preprocessed.xlsx', dtype=object, keep_default_na=False), config)
    train = prepared.set_index('record_id').loc[manifest['train']['record_ids']]
    test = prepared.set_index('record_id').loc[manifest['test']['record_ids']]
    model = joblib.load(root / 'model' / 'model_pipeline.joblib')
    preprocessor = model.named_steps['preprocessor']
    assert preprocessor.named_transformers_['numeric_0'].statistics_[0] == train['feature_0000'].median()
    vocabulary = preprocessor.named_transformers_['text_2'].vocabulary_
    for text in test['feature_0002']:
        token = text.split()[-1]
        assert token not in vocabulary
    assert set(preprocessor.named_transformers_['categorical_1'].categories_[0]) == set(train['feature_0001'])
    assert set(train.index).isdisjoint(test.index)
    for section in ('train', 'test'):
        assert min(manifest[section]['class_distribution'].values()) >= 2


def test_numeric_target_is_string_classification_and_reserved_headers_preserved(client, tmp_path):
    frame = pd.DataFrame({'record_id': [f'original-{i}' for i in range(40)], 'keputusan_laporan': [i for i in range(40)], 'numeric target': [i % 2 for i in range(40)]})
    buffer = BytesIO()
    frame.to_excel(buffer, sheet_name='Free sheet', index=False)
    job_id = upload(client, buffer.getvalue(), configure=False).json()['data']['job_id']
    response = configure(client, job_id, target_column='numeric target', features=[{'name': 'keputusan_laporan', 'kind': 'numeric'}])
    assert response.status_code == 200
    for stage in ('clean', 'preprocess', 'split', 'train', 'evaluate'):
        response = client.post(f'/api/jobs/{job_id}/{stage}')
        assert response.status_code == 200, response.text
    assert client.get(f'/api/jobs/{job_id}/prediction/schema').json()['data']['classes'] == ['0', '1']
    cleaned = pd.read_excel(tmp_path / 'storage' / 'jobs' / job_id / 'cleaned' / 'dataset_cleaned.xlsx')
    assert cleaned['source__record_id'].tolist() == frame['record_id'].tolist()
    assert cleaned['source__keputusan_laporan'].tolist() == frame['keputusan_laporan'].tolist()


def test_csv_separator_can_be_corrected_before_saving(client):
    content = generic_content(separator=';')
    job_id = upload(client, content, 'free.csv', configure=False).json()['data']['job_id']
    schema = client.get(f'/api/jobs/{job_id}/dataset/schema', params={'delimiter': ';', 'target_column': 'result'})
    assert schema.status_code == 200
    assert len(schema.json()['data']['columns']) == 5
    assert configure(client, job_id, sheet_name=None, delimiter=';').status_code == 200
    assert configure(client, job_id, sheet_name=None, delimiter=',').status_code == 422


def test_calendar_equivalent_features_share_group_and_conflicts_are_retained(client, tmp_path):
    rows = [[1, 'S', 'same text', '2030-01-01', 'A'], [1, 'S', 'same text', '2030-01-08', 'B']]
    rows += [[index + 10, 'S', f'other {index}', '2030-01-02', 'A' if index % 2 else 'B'] for index in range(30)]
    job_id = generic_job(client, rows=rows)
    assert client.post(f'/api/jobs/{job_id}/clean').json()['data']['rows_after'] == 32
    result = client.post(f'/api/jobs/{job_id}/preprocess')
    assert result.status_code == 200
    assert result.json()['data']['label_conflict_groups'] == 1
    frame = pd.read_excel(tmp_path / 'storage' / 'jobs' / job_id / 'preprocessed' / 'dataset_preprocessed.xlsx')
    assert frame.iloc[0]['near_duplicate_group_id'] == frame.iloc[1]['near_duplicate_group_id']
