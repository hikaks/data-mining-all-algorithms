from datetime import datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from app.core.config import get_settings
from app.core.dataset_contract import INPUT_LABEL_COLUMNS
from app.services.auto_labeling import classify_record
from app.services.dataset_labels import identify_raw_row
from app.storage.file_manager import write_excel_atomic
from tests.test_dataset import upload, workbook_bytes


def labeled_workbook_bytes(rows: list[list[object]], labels: list[str] | None = None) -> bytes:
    headers = get_settings().required_columns
    values = []
    for index, values_row in enumerate(rows):
        row = dict(zip(headers, values_row))
        audit = identify_raw_row(row, "2026-09-16T00:00:00+00:00")
        if labels is not None:
            label = labels[index]
            audit["keputusan_laporan"] = None if label == "NEEDS_REVIEW" else label
            audit["labeling_status"] = "NEEDS_REVIEW" if label == "NEEDS_REVIEW" else "LABELED"
            audit["label_validator_role"] = "ADMIN_VALIDATOR"
            audit["label_decision_reason"] = "Keputusan fixture independen yang disediakan dalam workbook."
            audit["label_policy_version"] = "test-fixture-v1"
            audit["label_confidence"] = None
        values.append([*values_row, *(audit[name] for name in INPUT_LABEL_COLUMNS)])
    return workbook_bytes(headers=(*headers, *INPUT_LABEL_COLUMNS), rows=values)


def _cleaned_job(client: TestClient, rows: list[list[object]] | None = None, labels: list[str] | None = None) -> str:
    content = labeled_workbook_bytes(rows, labels) if labels is not None else workbook_bytes(rows=rows)
    job_id = upload(client, content).json()["data"]["job_id"]
    assert client.post(f"/api/jobs/{job_id}/clean").status_code == 200
    return job_id


def _records(client: TestClient, job_id: str, label_filter: str = "ALL"):
    response = client.get(f"/api/jobs/{job_id}/labeling/records", params={"label_filter": label_filter, "page": 1, "page_size": 100})
    assert response.status_code == 200
    return response.json()["data"]["items"]


def test_raw_upload_identifies_every_row_and_keeps_raw_immutable(client: TestClient, tmp_path: Path) -> None:
    content = workbook_bytes()
    job_id = upload(client, content).json()["data"]["job_id"]
    path = tmp_path / "storage" / "jobs" / job_id
    snapshot = json.loads((path / "reports" / "input_labels.json").read_text("utf-8"))
    assert snapshot["source"] == "AUTO_IDENTIFIED"
    assert snapshot["decision_counts"] == {"SELESAI": 1, "TINDAK_LANJUT": 0, "NEEDS_REVIEW": 0}
    assert snapshot["rows"][0]["label_validator_role"] == "AI_VALIDATOR"
    assert snapshot["rows"][0]["label_decision_reason"]
    assert (path / "raw" / "dataset.xlsx").read_bytes() == content
    overview = client.get(f"/api/jobs/{job_id}").json()["data"]
    assert overview["input_label_source"] == "AUTO_IDENTIFIED"
    assert overview["input_label_counts"] == snapshot["decision_counts"]


def test_cleaning_transfers_labels_without_manual_step_and_preserves_audit(client: TestClient, tmp_path: Path) -> None:
    rows = [
        [2025, "PT.SST", "a.xlsx", "SST", 2, 1, datetime(2025, 1, 1), "Eman", "A", "Reset printer selesai", "OK", None],
        [2025, "PT.SST", "b.xlsx", "SST", 3, 2, datetime(2025, 1, 2), "Eman", "B", "Printer harus di service", "OK", None],
        [2025, "PT.SST", "c.xlsx", "SST", 4, 3, datetime(2025, 1, 3), "Eman", "C", "Catatan perangkat", None, None],
    ]
    job_id = _cleaned_job(client, rows)
    records = _records(client, job_id)
    assert [row["keputusan_laporan"] for row in records] == ["SELESAI", "TINDAK_LANJUT", None]
    assert records[2]["labeling_status"] == "NEEDS_REVIEW"
    assert all(row["label_validator_role"] == "AI_VALIDATOR" for row in records)
    assert all(row["label_decision_reason"] and row["label_policy_version"] == "ai-assisted-id-v1" for row in records)
    report = client.get(f"/api/jobs/{job_id}/labeling/report").json()["data"]
    assert len(report["events"]) == 3
    assert all(event["operation"] == "UPLOAD_AUTO_IDENTIFY" for event in report["events"])
    assert report["statistics"]["unlabeled_records"] == 0
    assert client.get(f"/api/jobs/{job_id}").json()["data"]["status"] == "LABELED"
    assert client.get(f"/api/jobs/{job_id}/download/labeled").status_code == 200
    path = tmp_path / "storage" / "jobs" / job_id
    assert pd.read_excel(path / "cleaned" / "dataset_cleaned.xlsx")["keputusan_laporan"].notna().sum() == 2


def test_import_preserves_provided_decision_not_regex_result(client: TestClient, tmp_path: Path) -> None:
    rows = [[2025, "PT.SST", "a.xlsx", "SST", 2, 1, datetime(2025, 1, 1), "Eman", "A", "Pekerjaan selesai", "OK", None]]
    content = labeled_workbook_bytes(rows, ["TINDAK_LANJUT"])
    job_id = upload(client, content).json()["data"]["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["data"]["input_label_source"] == "IMPORTED"
    assert client.post(f"/api/jobs/{job_id}/clean").status_code == 200
    row = _records(client, job_id)[0]
    assert row["keputusan_laporan"] == "TINDAK_LANJUT"
    assert row["label_validator_role"] == "ADMIN_VALIDATOR"
    assert row["label_policy_version"] == "test-fixture-v1"
    assert row["label_confidence"] is None
    assert (tmp_path / "storage" / "jobs" / job_id / "raw" / "dataset.xlsx").read_bytes() == content


@pytest.mark.parametrize(("column", "value"), [
    ("keputusan_laporan", "ESKALASI"),
    ("labeling_status", "UNLABELED"),
    ("label_validator_role", "FAKE"),
    ("label_decision_reason", ""),
    ("label_policy_version", ""),
    ("label_confidence", 1.5),
    ("label_confidence", "NaN"),
    ("label_updated_at", "invalid date"),
])
def test_invalid_imported_labels_cannot_configure_preset(client: TestClient, tmp_path: Path, column: str, value: object) -> None:
    values = [2025, "PT.SST", "a.xlsx", "SST", 2, 1, datetime(2025, 1, 1), "Eman", "A", "Selesai", "OK", None]
    audit = identify_raw_row(dict(zip(get_settings().required_columns, values)), "2026-09-16T00:00:00+00:00")
    audit[column] = value
    content = workbook_bytes(headers=(*get_settings().required_columns, *INPUT_LABEL_COLUMNS), rows=[[*values, *(audit[name] for name in INPUT_LABEL_COLUMNS)]])
    response = upload(client, content)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"
    jobs = list((tmp_path / 'storage' / 'jobs').iterdir())
    assert len(jobs) == 1
    assert json.loads((jobs[0] / 'config' / 'job.json').read_text('utf-8'))['status'] == 'UPLOADED'
    assert not (jobs[0] / 'config' / 'dataset_config.json').exists()


def test_needs_review_must_have_empty_target(client: TestClient) -> None:
    values = [2025, "PT.SST", "a.xlsx", "SST", 2, 1, None, "Eman", "A", "Selesai", "OK", None]
    audit = identify_raw_row(dict(zip(get_settings().required_columns, values)), "2026-09-16T00:00:00+00:00")
    audit["labeling_status"] = "NEEDS_REVIEW"
    content = workbook_bytes(headers=(*get_settings().required_columns, *INPUT_LABEL_COLUMNS), rows=[[*values, *(audit[name] for name in INPUT_LABEL_COLUMNS)]])
    assert upload(client, content).status_code == 422


def test_partial_label_header_is_rejected(client: TestClient) -> None:
    headers = (*get_settings().required_columns, "keputusan_laporan")
    assert upload(client, workbook_bytes(headers=headers)).status_code == 422


def test_duplicate_conflicting_labels_are_not_silently_removed(client: TestClient, tmp_path: Path) -> None:
    row = [2025, "PT.SST", "a.xlsx", "SST", 2, 1, datetime(2025, 1, 1), "Eman", "A", "Selesai", "OK", None]
    job_id = upload(client, labeled_workbook_bytes([row, row], ["SELESAI", "TINDAK_LANJUT"])).json()["data"]["job_id"]
    response = client.post(f"/api/jobs/{job_id}/clean")
    assert response.status_code == 422
    assert "bertentangan" in response.json()["error"]["message"]
    path = tmp_path / "storage" / "jobs" / job_id
    assert not (path / "cleaned" / "dataset_cleaned.xlsx").exists()


def test_manual_label_mutation_routes_are_removed(client: TestClient) -> None:
    job_id = _cleaned_job(client)
    record_id = _records(client, job_id)[0]["record_id"]
    before = client.get(f"/api/jobs/{job_id}/labeling/report").json()
    for suffix in ("initialize", "auto", "bulk"):
        assert client.post(f"/api/jobs/{job_id}/labeling/{suffix}", json={}).status_code == 404
    assert client.patch(f"/api/jobs/{job_id}/labeling/records/{record_id}", json={"label": "TINDAK_LANJUT"}).status_code == 404
    assert client.get(f"/api/jobs/{job_id}/labeling/report").json() == before


def test_existing_policy_remains_deterministic_and_honest() -> None:
    assert classify_record({"keluhan_solusi": "Printer harus di service", "status": "OK"}).label == "TINDAK_LANJUT"
    assert classify_record({"keluhan_solusi": "Printer normal", "status": "OK"}).label == "SELESAI"
    assert classify_record({"keluhan_solusi": "", "status": "OK"}).label == "NEEDS_REVIEW"
