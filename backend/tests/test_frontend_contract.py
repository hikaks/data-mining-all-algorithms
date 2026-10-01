from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_dataset import upload, workbook_bytes
from tests.test_labeling import _cleaned_job, _records
from tests.test_prediction import _evaluated_job


def test_compact_cleaning_report_preserves_summary_and_artifact(client: TestClient, tmp_path: Path) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]
    assert client.post(f"/api/jobs/{job_id}/clean").status_code == 200
    report_path = tmp_path / "storage" / "jobs" / job_id / "reports" / "cleaning_report.json"
    before = report_path.read_bytes()
    full_response = client.get(f"/api/jobs/{job_id}/cleaning-report")
    assert full_response.status_code == 200, full_response.text
    full = full_response.json()["data"]
    assert all(isinstance(value, int) for value in full["normalization"].values())
    response = client.get(f"/api/jobs/{job_id}/cleaning-report?include_details=false")
    assert response.status_code == 200
    compact = response.json()["data"]
    for section in ("invalid_dates", "incomplete_records", "duplicate_records", "operations", "removed_empty_records", "potential_duplicates"):
        assert compact[section] == []
    assert compact["rows_after"] == full["rows_after"]
    assert compact["normalization"] == full["normalization"]
    assert full["incomplete_records"]
    assert report_path.read_bytes() == before


def test_labeling_report_limit_returns_recent_events_without_truncating_file(client: TestClient, tmp_path: Path) -> None:
    from datetime import datetime
    rows = [[2025, "PT.SST", f"{index}.xlsx", "SST", index + 2, index, datetime(2025, 1, index + 1), "Eman", "A", f"Selesai {index}", "OK", None] for index in range(2)]
    job_id = _cleaned_job(client, rows)
    report_path = tmp_path / "storage" / "jobs" / job_id / "reports" / "labeling_report.json"
    before = report_path.read_bytes()
    full = client.get(f"/api/jobs/{job_id}/labeling/report").json()["data"]
    limited = client.get(f"/api/jobs/{job_id}/labeling/report?limit=1")
    assert limited.status_code == 200
    assert limited.json()["data"]["events"] == full["events"][-1:]
    assert len(full["events"]) == 2
    assert report_path.read_bytes() == before
    assert client.get(f"/api/jobs/{job_id}/labeling/report?limit=0").status_code == 422


def test_evaluated_job_can_be_connected_without_reopening_labeling(client: TestClient, tmp_path: Path) -> None:
    job_id = _evaluated_job(client)
    job_path = tmp_path / "storage" / "jobs" / job_id
    metadata_path = job_path / "config" / "job.json"
    before = metadata_path.read_bytes()
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "EVALUATED"
    assert all(result["artifacts"][key] for key in ("raw", "cleaned", "labeled", "preprocessed", "split", "model", "evaluation"))
    assert result["artifacts"]["predictions"] is False
    assert client.get(f"/api/jobs/{job_id}/labeling/records?page_size=25").status_code == 200
    assert client.post(f"/api/jobs/{job_id}/labeling/initialize").status_code == 404
    assert metadata_path.read_bytes() == before
