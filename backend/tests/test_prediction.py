import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from tests.test_evaluation import _trained_job


VALID_INPUT = {
    "tanggal": "2026-04-01",
    "customer": "SST",
    "teknisi": "Eman | Harry",
    "text_laporan": "Laptop harus dibawa ke kantor untuk service lanjutan",
}


def _evaluated_job(client: TestClient) -> str:
    job_id = _trained_job(client)
    assert client.post(f"/api/jobs/{job_id}/evaluate").status_code == 200
    return job_id


def test_prediction_and_actual_decision_history_are_append_only(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _evaluated_job(client)
    job_root = tmp_path / "storage" / "jobs" / job_id
    model_path = job_root / "model" / "model_pipeline.joblib"
    model_before = model_path.read_bytes()

    response = client.post(f"/api/jobs/{job_id}/predict", json=VALID_INPUT)

    assert response.status_code == 200
    prediction = response.json()["data"]
    assert prediction["prediction"] in {"SELESAI", "TINDAK_LANJUT"}
    assert set(prediction["probabilities"]) == {"SELESAI", "TINDAK_LANJUT"}
    assert sum(prediction["probabilities"].values()) == pytest.approx(1.0)
    assert prediction["confidence"] == prediction["probabilities"][
        prediction["prediction"]
    ]
    assert prediction["recommendation_only"] is True
    assert prediction["actual_decision"] is None
    assert model_path.read_bytes() == model_before

    history_path = job_root / "predictions" / "predictions.jsonl"
    first_bytes = history_path.read_bytes()
    first_events = [json.loads(line) for line in first_bytes.decode().splitlines()]
    assert len(first_events) == 1
    assert first_events[0]["event_type"] == "prediction_created"
    assert first_events[0]["input"]["tanggal"] == VALID_INPUT["tanggal"]

    history_response = client.get(f"/api/jobs/{job_id}/predictions")
    assert history_response.status_code == 200
    history = history_response.json()["data"]
    assert history["total_items"] == 1
    assert history["event_count"] == 1
    assert history["items"][0]["prediction_id"] == prediction["prediction_id"]

    decision_response = client.patch(
        f"/api/jobs/{job_id}/predictions/{prediction['prediction_id']}/actual-decision",
        json={"actual_decision": "TINDAK_LANJUT"},
    )
    assert decision_response.status_code == 200
    decision = decision_response.json()["data"]
    assert decision["actual_decision"] == "TINDAK_LANJUT"
    assert decision["validator_role"] == "ADMIN_VALIDATOR"
    second_bytes = history_path.read_bytes()
    assert second_bytes.startswith(first_bytes)
    second_events = [json.loads(line) for line in second_bytes.decode().splitlines()]
    assert len(second_events) == 2
    assert second_events[1]["event_type"] == "actual_decision_recorded"

    idempotent = client.patch(
        f"/api/jobs/{job_id}/predictions/{prediction['prediction_id']}/actual-decision",
        json={"actual_decision": "TINDAK_LANJUT"},
    )
    assert idempotent.status_code == 200
    assert history_path.read_bytes() == second_bytes

    missing_reason = client.patch(
        f"/api/jobs/{job_id}/predictions/{prediction['prediction_id']}/actual-decision",
        json={"actual_decision": "SELESAI"},
    )
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["code"] == "INVALID_DATASET"

    changed = client.patch(
        f"/api/jobs/{job_id}/predictions/{prediction['prediction_id']}/actual-decision",
        json={
            "actual_decision": "SELESAI",
            "reason": "Hasil pemeriksaan admin menunjukkan pekerjaan sudah selesai.",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["actual_decision"] == "SELESAI"
    third_bytes = history_path.read_bytes()
    assert third_bytes.startswith(second_bytes)
    assert len(third_bytes.decode().splitlines()) == 3

    final_history = client.get(f"/api/jobs/{job_id}/predictions").json()["data"]
    assert final_history["event_count"] == 3
    assert final_history["items"][0]["actual_decision"] == "SELESAI"
    download = client.get(f"/api/jobs/{job_id}/download/predictions")
    assert download.status_code == 200
    assert download.content == third_bytes


def test_prediction_rejects_invalid_input_without_writing_history(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _evaluated_job(client)

    response = client.post(
        f"/api/jobs/{job_id}/predict",
        json={**VALID_INPUT, "text_laporan": "  ", "status": "OK"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert not (
        tmp_path / "storage" / "jobs" / job_id / "predictions" / "predictions.jsonl"
    ).exists()


def test_prediction_rejects_missing_model(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _evaluated_job(client)
    model_path = (
        tmp_path
        / "storage"
        / "jobs"
        / job_id
        / "model"
        / "model_pipeline.joblib"
    )
    model_path.unlink()

    response = client.post(f"/api/jobs/{job_id}/predict", json=VALID_INPUT)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"
