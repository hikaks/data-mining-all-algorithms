from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
import pandas as pd

from tests.test_dataset import upload, workbook_bytes
from tests.test_labeling import _cleaned_job, _records


def _split_ready_job(client: TestClient) -> str:
    rows: list[list[object]] = []
    start = datetime(2025, 1, 1)
    for index in range(20):
        is_follow_up = index >= 10
        if index in {0, 1}:
            report = "Reset printer dan cek jaringan"
        else:
            prefix = "Lanjut penggantian perangkat" if is_follow_up else "Pekerjaan selesai"
            report = f"{prefix} nomor {index}"
        rows.append(
            [
                2025,
                "PT.SST",
                f"{index}.xlsx",
                "SST",
                index + 2,
                index + 1,
                start + timedelta(days=index),
                "Eman" if index % 2 == 0 else "Harry",
                f"User {index}",
                report,
                "OK",
                None,
            ]
        )

    job_id = _cleaned_job(client, rows, ["SELESAI"] * 10 + ["TINDAK_LANJUT"] * 10)
    assert client.post(f"/api/jobs/{job_id}/preprocess").status_code == 200
    return job_id


def test_split_is_deterministic_stratified_and_group_isolated(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _split_ready_job(client)

    response = client.post(f"/api/jobs/{job_id}/split")

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "PREPROCESSED"
    assert result["strategy"] == "StratifiedGroupKFold"
    assert result["random_state"] == 42
    assert result["train_rows"] + result["test_rows"] == 20
    assert result["train_distribution"]["SELESAI"] > 0
    assert result["train_distribution"]["TINDAK_LANJUT"] > 0
    assert result["test_distribution"]["SELESAI"] >= 2
    assert result["test_distribution"]["TINDAK_LANJUT"] >= 2
    assert result["group_overlap_count"] == 0
    assert result["record_overlap_count"] == 0

    manifest_response = client.get(f"/api/jobs/{job_id}/split-manifest")
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()["data"]
    train_ids = set(manifest["train"]["record_ids"])
    test_ids = set(manifest["test"]["record_ids"])
    assert not train_ids.intersection(test_ids)
    assert len(train_ids.union(test_ids)) == 20
    assert manifest["validation"]["passed"] is True
    assert manifest["configuration"]["sampling"] == "NONE"
    assert manifest["source_artifact"]["sha256"]

    preprocessed = pd.read_excel(
        tmp_path
        / "storage"
        / "jobs"
        / job_id
        / "preprocessed"
        / "dataset_preprocessed.xlsx",
        sheet_name="DATA_PREPROCESSED",
    )
    repeated = preprocessed.loc[
        preprocessed["text_laporan"] == "Reset printer dan cek jaringan", "record_id"
    ].astype(str)
    assert len(repeated) == 2
    assert set(repeated).issubset(train_ids) or set(repeated).issubset(test_ids)

    repeated_response = client.post(f"/api/jobs/{job_id}/split")
    download = client.get(f"/api/jobs/{job_id}/download/split-manifest")
    assert repeated_response.status_code == 200
    assert repeated_response.json()["data"] == result
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/json")


def test_split_rejects_job_before_preprocessing(client: TestClient) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]

    response = client.post(f"/api/jobs/{job_id}/split")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_JOB_STATE"
