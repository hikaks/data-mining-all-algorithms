"""Real-data QA: only an isolated container, with production storage mounted read-only."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import httpx
import joblib

from app.core.config import get_settings

JOB_ID = 'RAHib9nFcP5jfOY5Ihp08A'
ROOT = Path('/tmp/svm-convergence-qa')


def hashes(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    assert get_settings().storage_root == ROOT, 'QA must not use production storage.'
    source = Path('/input-storage/jobs') / JOB_ID
    destination = ROOT / 'jobs' / JOB_ID
    assert source.is_dir() and not destination.exists()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    original = hashes(destination)
    results = []
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=None) as client:
        base = f'/api/jobs/{JOB_ID}'
        def request(method, path, **kwargs):
            response = client.request(method, base + path, **kwargs)
            assert response.is_success, response.text
            return response.json()['data']
        previous = request('GET', '/experiments')
        initial_active = previous['active_experiment_id']
        test_ids = {}
        for ratio in (0.25, 0.2, 0.3):
            for algorithm in ('svm_linear', 'random_forest', 'decision_tree', 'knn'):
                experiment = request('POST', '/experiments', json={'test_ratio': ratio, 'algorithm': algorithm})
                eid = experiment['experiment_id']
                print(json.dumps({'event': 'start', 'ratio': ratio, 'algorithm': algorithm, 'experiment_id': eid}), flush=True)
                prefix = '/experiments/' + eid
                split = request('POST', prefix + '/split')
                assert split['group_overlap_count'] == split['record_overlap_count'] == 0
                trained = request('POST', prefix + '/train')
                request('POST', prefix + '/evaluate')
                detail = request('GET', prefix)
                metadata = request('GET', prefix + '/model-metadata')
                model = joblib.load(destination / 'experiments' / eid / 'model/model_pipeline.joblib')
                assert detail['status'] == 'EVALUATED' and metadata['verification']['model_reload_passed']
                assert detail['test_set_id'] == test_ids.setdefault(ratio, detail['test_set_id'])
                solver = metadata['verification'].get('svm_solver')
                if algorithm == 'svm_linear':
                    assert model.named_steps['classifier'].estimator_.fit_status_ == 0
                    assert solver['converged'] and solver['max_iter'] == -1
                result = dict(experiment_id=eid, algorithm=algorithm, test_ratio=ratio,
                    actual_test_ratio=detail['actual_test_ratio'], status=detail['status'],
                    training_seconds=trained['training_seconds'], accuracy=detail['metrics']['accuracy'],
                    macro_f1=detail['metrics']['macro_average']['f1'], solver=solver)
                results.append(result)
                print(json.dumps({'event': 'evaluated', **result}), flush=True)
        assert request('GET', '/experiments')['active_experiment_id'] == initial_active
    current = hashes(destination)
    assert all(current[path] == digest for path, digest in original.items())
    evidence = dict(job_id=JOB_ID, original_files_unchanged=len(original), active_model_unchanged=True, results=results)
    (ROOT / 'qa-results.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps({'event': 'complete', **evidence}), flush=True)


if __name__ == '__main__':
    main()
