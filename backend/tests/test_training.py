from pathlib import Path

from fastapi.testclient import TestClient
import joblib
import pandas as pd

from app.services.preprocessing_pipeline import MODEL_FEATURES
from tests.test_dataset import upload, workbook_bytes
from tests.test_splitting import _split_ready_job


def test_training_persists_reloadable_pipeline_and_metadata(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _split_ready_job(client)
    split_response = client.post(f"/api/jobs/{job_id}/split")
    assert split_response.status_code == 200

    response = client.post(f"/api/jobs/{job_id}/train")

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "TRAINED"
    assert result["algorithm"] == "RandomForestClassifier"
    assert result["training_version"] == "random-forest-baseline-v1"
    assert result["trained_rows"] == split_response.json()["data"]["train_rows"]
    assert set(result["classes"]) == {"SELESAI", "TINDAK_LANJUT"}
    assert result["transformed_feature_count"] > len(MODEL_FEATURES)

    job_root = tmp_path / "storage" / "jobs" / job_id
    model_path = job_root / "model" / "model_pipeline.joblib"
    metadata_path = job_root / "model" / "model_metadata.json"
    assert model_path.is_file()
    assert metadata_path.is_file()

    metadata_response = client.get(f"/api/jobs/{job_id}/model-metadata")
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()["data"]
    assert metadata["model_id"] == result["model_id"]
    assert metadata["configuration"]["parameters"]["class_weight"] == "balanced"
    assert metadata["configuration"]["parameters"]["n_jobs"] == 1
    assert metadata["configuration"]["hyperparameter_search"] == "NONE"
    assert metadata["training_data"]["test_set_used_for_fit"] is False
    assert metadata["verification"]["model_reload_passed"] is True
    assert metadata["artifacts"]["model_pipeline"]["sha256"]
    assert metadata["dependencies"]["scikit-learn"]

    manifest = client.get(f"/api/jobs/{job_id}/split-manifest").json()["data"]
    dataframe = pd.read_excel(
        job_root / "preprocessed" / "dataset_preprocessed.xlsx",
        sheet_name="DATA_PREPROCESSED",
    )
    sample = dataframe.loc[
        dataframe["record_id"].astype(str).isin(manifest["test"]["record_ids"]),
        list(MODEL_FEATURES),
    ].head(2)
    pipeline = joblib.load(model_path)
    predictions = pipeline.predict(sample)
    assert len(predictions) == 2
    assert set(predictions).issubset({"SELESAI", "TINDAK_LANJUT"})

    repeated = client.post(f"/api/jobs/{job_id}/train")
    download = client.get(f"/api/jobs/{job_id}/download/model")
    assert repeated.status_code == 200
    assert repeated.json()["data"] == result
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/octet-stream")


def test_training_requires_split_manifest(client: TestClient) -> None:
    job_id = _split_ready_job(client)

    response = client.post(f"/api/jobs/{job_id}/train")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_training_rejects_job_before_preprocessing(client: TestClient) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]

    response = client.post(f"/api/jobs/{job_id}/train")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_JOB_STATE"
