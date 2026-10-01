from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sklearn.metrics import accuracy_score, balanced_accuracy_score

from tests.test_splitting import _split_ready_job


def _trained_job(client: TestClient) -> str:
    job_id = _split_ready_job(client)
    assert client.post(f"/api/jobs/{job_id}/split").status_code == 200
    assert client.post(f"/api/jobs/{job_id}/train").status_code == 200
    return job_id


def test_evaluation_uses_fixed_test_set_and_persists_auditable_metrics(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _trained_job(client)
    job_root = tmp_path / "storage" / "jobs" / job_id
    model_path = job_root / "model" / "model_pipeline.joblib"
    model_bytes_before = model_path.read_bytes()
    manifest = client.get(f"/api/jobs/{job_id}/split-manifest").json()["data"]

    response = client.post(f"/api/jobs/{job_id}/evaluate")

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "EVALUATED"
    assert result["evaluation_version"] == "fixed-test-evaluation-v1"
    assert result["evaluated_rows"] == manifest["test"]["row_count"]
    assert result["actual_distribution"] == manifest["test"]["class_distribution"]
    assert result["positive_class"] == "TINDAK_LANJUT"
    assert 0 <= result["accuracy"] <= 1
    assert 0 <= result["balanced_accuracy"] <= 1
    assert model_path.read_bytes() == model_bytes_before

    report_response = client.get(f"/api/jobs/{job_id}/evaluation")
    assert report_response.status_code == 200
    report = report_response.json()["data"]
    assert report["evaluation_scope"]["dataset_partition"] == "TEST_ONLY"
    assert report["evaluation_scope"]["test_set_used_for_parameter_selection"] is False
    assert [item["record_id"] for item in report["prediction_audit"]] == manifest[
        "test"
    ]["record_ids"]
    actual = [item["actual"] for item in report["prediction_audit"]]
    predicted = [item["predicted"] for item in report["prediction_audit"]]
    assert report["metrics"]["accuracy"] == pytest.approx(
        accuracy_score(actual, predicted)
    )
    assert report["metrics"]["balanced_accuracy"] == pytest.approx(
        balanced_accuracy_score(actual, predicted)
    )
    assert sum(sum(row) for row in report["confusion_matrix"]["values"]) == len(
        actual
    )
    assert set(report["classification_report"]).issuperset(
        {"SELESAI", "TINDAK_LANJUT", "accuracy", "macro avg", "weighted avg"}
    )

    importance_response = client.get(f"/api/jobs/{job_id}/feature-importance")
    assert importance_response.status_code == 200
    importance = importance_response.json()["data"]
    assert importance["method"] == "mean_decrease_in_impurity"
    assert importance["feature_count"] == len(importance["features"])
    assert importance["feature_count"] > 0
    assert importance["features"][0]["rank"] == 1
    assert importance["limitations"]

    repeated = client.post(f"/api/jobs/{job_id}/evaluate")
    evaluation_download = client.get(f"/api/jobs/{job_id}/download/evaluation")
    importance_download = client.get(
        f"/api/jobs/{job_id}/download/feature-importance"
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"] == result
    assert evaluation_download.status_code == 200
    assert importance_download.status_code == 200
    assert (job_root / "reports" / "evaluation.json").is_file()
    assert (job_root / "reports" / "feature_importance.json").is_file()


def test_evaluation_rejects_job_before_training(client: TestClient) -> None:
    job_id = _split_ready_job(client)
    assert client.post(f"/api/jobs/{job_id}/split").status_code == 200

    response = client.post(f"/api/jobs/{job_id}/evaluate")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_JOB_STATE"
