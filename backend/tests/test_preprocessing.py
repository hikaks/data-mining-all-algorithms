from datetime import datetime
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from app.services.preprocessing_pipeline import (
    MODEL_FEATURES,
    assert_feature_contract,
    assert_finite_matrix,
    build_model_preprocessor,
)
from tests.test_dataset import upload, workbook_bytes
from tests.test_labeling import _cleaned_job, _records
from app.core.config import get_settings
from app.services.labeling_service import LabelingService
from app.storage.file_manager import read_json, write_json_atomic


def _preprocessing_ready_job(client: TestClient) -> str:
    rows = [
        [2025, "PT.SST", "a.xlsx", "SST", 2, 1, datetime(2025, 1, 1), "Eman", "User A", "Reset printer dan cek jaringan", "OK", None],
        [2025, "PT.SST", "b.xlsx", "SST", 3, 2, datetime(2025, 1, 8), "Eman", "User B", "Reset printer dan cek jaringan", "OK", None],
        [2025, "PT.SST", "c.xlsx", "SST", 4, 3, datetime(2025, 2, 1), "Harry", "User C", "Printer harus di service", "OK", None],
        [2025, "PT.SST", "d.xlsx", "SST", 5, 4, datetime(2025, 2, 2), "Harry", "User D", "Menunggu sparepart printer", "OK", None],
        [2026, "PT.SST", "e.xlsx", "SST", 6, 5, datetime(2026, 12, 1), "Eman", "User E", "Pekerjaan luar periode", "OK", None],
        [2025, "PT.SST", "f.xlsx", "SST", 7, 6, datetime(2025, 3, 1), "Eman", "User F", "Catatan belum cukup", None, None],
    ]
    return _cleaned_job(client, rows)


def test_preprocess_creates_leakage_safe_artifacts_and_near_duplicate_groups(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _preprocessing_ready_job(client)

    response = client.post(f"/api/jobs/{job_id}/preprocess")

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "PREPROCESSED"
    assert result["source_rows"] == 6
    assert result["output_rows"] == 4
    assert result["excluded_rows"] == 2
    assert result["target_distribution"] == {"SELESAI": 2, "TINDAK_LANJUT": 2}
    assert result["near_duplicate_groups"] == 1
    assert result["near_duplicate_pairs"] == 1

    job_path = tmp_path / "storage" / "jobs" / job_id
    output_path = job_path / "preprocessed" / "dataset_preprocessed.xlsx"
    dataframe = pd.read_excel(output_path, sheet_name="DATA_PREPROCESSED")
    assert list(dataframe.columns) == [
        "record_id",
        "near_duplicate_group_id",
        *MODEL_FEATURES,
        "keputusan_laporan",
    ]
    duplicate_groups = dataframe["near_duplicate_group_id"].value_counts()
    assert int(duplicate_groups.max()) == 2
    report = client.get(f"/api/jobs/{job_id}/preprocessing-report").json()["data"]
    assert report["excluded_counts"] == {
        "INVALID_DATE_OUTSIDE_RESEARCH_PERIOD": 1,
        "LABEL_NOT_FINAL": 1,
    }
    assert report["leakage_audit"]["passed"] is True
    assert report["transformer_spec"]["learned_transformations_fitted"] is False
    assert report["transformer_spec"]["fit_policy"] == "FIT_ON_TRAIN_ONLY"
    assert report["near_duplicate_evaluation"]["automatic_removal"] is False
    assert report["artifact_integrity"]["input_labeled_sha256"]
    assert report["artifact_integrity"]["output_preprocessed_sha256"]

    repeated = client.post(f"/api/jobs/{job_id}/preprocess")
    download = client.get(f"/api/jobs/{job_id}/download/preprocessed")
    assert repeated.status_code == 200
    assert repeated.json()["data"] == result
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_column_transformer_contract_fits_train_only_and_is_finite() -> None:
    dataframe = pd.DataFrame(
        {
            "text_laporan": ["reset printer", "menunggu sparepart", "cek jaringan"],
            "customer": ["PT A", "PT A", "PT B"],
            "teknisi": ["Eman", "Harry", None],
            "tahun": [2025, 2025, 2026],
            "bulan": [1, 2, 3],
            "hari_dalam_minggu": [1, 2, 3],
            "jumlah_teknisi": [1, 1, 1],
        }
    )
    assert_feature_contract(list(dataframe.columns))
    transformer = build_model_preprocessor()
    transformed = transformer.fit_transform(dataframe.iloc[:2])
    assert transformed.shape[0] == 2
    assert_finite_matrix(transformed)
    test_transformed = transformer.transform(dataframe.iloc[2:])
    assert test_transformed.shape[0] == 1
    assert_finite_matrix(test_transformed)

    with pytest.raises(ValueError, match="leakage"):
        assert_feature_contract([*MODEL_FEATURES, "status"])


def test_legacy_cleaned_job_continues_without_manual_labeling(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _preprocessing_ready_job(client)
    job_path = tmp_path / "storage" / "jobs" / job_id
    # These are disposable fixture artifacts, not the operator's storage.
    (job_path / "labeled" / "dataset_labeled.xlsx").unlink()
    for name in ("labeling_report.json", "input_labels.json"):
        (job_path / "reports" / name).unlink()
    metadata_path = job_path / "config" / "job.json"
    metadata = read_json(metadata_path)
    metadata["status"] = "CLEANED"
    for name in ("input_label_source", "input_label_counts"):
        metadata.pop(name, None)
    write_json_atomic(metadata_path, metadata)
    raw_path = job_path / "raw" / "dataset.xlsx"
    raw_hash = sha256(raw_path.read_bytes()).hexdigest()

    response = client.post(f"/api/jobs/{job_id}/preprocess")

    assert response.status_code == 200
    assert response.json()["data"]["output_rows"] == 4
    assert read_json(metadata_path)["input_label_source"] == "AUTO_IDENTIFIED"
    assert sha256(raw_path.read_bytes()).hexdigest() == raw_hash
    assert not (job_path / "model" / "model_pipeline.joblib").exists()


def test_legacy_pending_labels_preserve_existing_decisions_and_audit(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _preprocessing_ready_job(client)
    job_path = tmp_path / "storage" / "jobs" / job_id
    labeled_path = job_path / "labeled" / "dataset_labeled.xlsx"
    dataframe = pd.read_excel(labeled_path, sheet_name="DATA_LABELED", dtype=object)
    dataframe.at[0, "label_validator_role"] = "ADMIN_VALIDATOR"
    dataframe.at[0, "label_decision_reason"] = "Keputusan lama harus tetap utuh."
    preserved = dataframe.iloc[0].fillna("").to_dict()
    review = dataframe.iloc[5].fillna("").to_dict()
    dataframe.at[1, "keputusan_laporan"] = None
    dataframe.at[1, "labeling_status"] = "UNLABELED"
    report_path = job_path / "reports" / "labeling_report.json"
    report = read_json(report_path)
    old_events = report["events"].copy()
    settings = replace(get_settings(), storage_root=tmp_path / "storage")
    LabelingService(settings)._persist(job_id, dataframe, report)

    response = client.post(f"/api/jobs/{job_id}/preprocess")

    assert response.status_code == 200
    result = pd.read_excel(labeled_path, sheet_name="DATA_LABELED", dtype=object)
    assert result.iloc[0].fillna("").to_dict() == preserved
    assert result.iloc[5].fillna("").to_dict() == review
    assert result.at[1, "labeling_status"] == "LABELED"
    assert result.at[1, "label_validator_role"] == "AI_VALIDATOR"
    assert read_json(report_path)["events"][:len(old_events)] == old_events


def test_partial_legacy_label_artifacts_are_rejected_without_overwrite(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = _preprocessing_ready_job(client)
    job_path = tmp_path / "storage" / "jobs" / job_id
    labeled_path = job_path / "labeled" / "dataset_labeled.xlsx"
    before = labeled_path.read_bytes()
    (job_path / "reports" / "labeling_report.json").unlink()

    response = client.post(f"/api/jobs/{job_id}/preprocess")

    assert response.status_code == 422
    assert labeled_path.read_bytes() == before
    assert not (job_path / "preprocessed" / "dataset_preprocessed.xlsx").exists()


def test_preprocess_rejects_job_before_cleaning_and_cannot_relabel_afterward(
    client: TestClient,
) -> None:
    raw_job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]
    rejected = client.post(f"/api/jobs/{raw_job_id}/preprocess")
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "INVALID_JOB_STATE"

    job_id = _preprocessing_ready_job(client)
    record_id = _records(client, job_id)[0]["record_id"]
    assert client.post(f"/api/jobs/{job_id}/preprocess").status_code == 200
    relabel = client.patch(
        f"/api/jobs/{job_id}/labeling/records/{record_id}",
        json={"label": "TINDAK_LANJUT", "reason": "Percobaan setelah freeze."},
    )
    assert relabel.status_code == 404
