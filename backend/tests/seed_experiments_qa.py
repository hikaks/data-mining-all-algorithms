"""Disposable browser fixtures only. Refuse all paths except the named QA root."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.main import create_app
from tests.test_experiments import ready, create, run
from tests.test_generic import generic_job
from tests.test_splitting import _split_ready_job


if __name__ == '__main__':
    settings = get_settings()
    assert settings.storage_root.resolve() == Path('/tmp/experiments-qa'), 'QA storage isolation required'
    with TestClient(create_app(settings)) as client:
        binary = ready(client)
        multi = ready(client, ('A', 'B', 'C'))
        for stage in ('split', 'train', 'evaluate'):
            response = client.post(f'/api/jobs/{multi}/{stage}')
            assert response.status_code == 200, response.text
        pt = _split_ready_job(client)
        rows = [[1, 'S', 'same text', '2030-01-01', 'A'], [1, 'S', 'same text', '2030-01-01', 'B']]
        failed = generic_job(client, rows=rows)
        client.post(f'/api/jobs/{failed}/clean'); client.post(f'/api/jobs/{failed}/preprocess')
        print(json.dumps({'binary': binary, 'multiclass_legacy': multi, 'maxkomp': pt, 'insufficient_groups': failed}))
