from io import BytesIO
from datetime import datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.config import get_settings


def workbook_bytes(
    headers: tuple[str, ...] | None = None,
    rows: list[list[object]] | None = None,
    sheet_name: str = "DATA_MENTAH",
) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet.append(list(headers or get_settings().required_columns))
    for row in rows or [[2025, "PT.SST", "source.xlsx", "SST", 2, 1, None, "Eman", "User", "Perbaikan", "OK", None]]:
        worksheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, content: bytes, filename: str = "dataset.xlsx", *, configure: bool = True):
    """PT regression fixture: upload then explicitly save the official preset."""
    response = client.post(
        "/api/dataset/upload",
        files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    if configure and response.status_code == 201:
        configuration = client.put(f"/api/jobs/{response.json()['data']['job_id']}/dataset/configuration", json={'profile': 'maxkomp', 'sheet_name': 'DATA_MENTAH', 'target_column': 'keputusan_laporan', 'features': []})
        if configuration.status_code != 200:
            return configuration
    return response


def test_upload_creates_immutable_raw_job_and_summary(
    client: TestClient, tmp_path: Path
) -> None:
    content = workbook_bytes()
    response = upload(client, content, "laporan asli.xlsx")

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["row_count"] == 1
    assert payload["data"]["original_filename"] == "laporan asli.xlsx"

    job_id = payload["data"]["job_id"]
    job_path = tmp_path / "storage" / "jobs" / job_id
    assert (job_path / "raw" / "dataset.xlsx").read_bytes() == content
    assert (job_path / "reports" / "data_understanding.json").is_file()
    metadata = json.loads((job_path / "config" / "job.json").read_text("utf-8"))
    assert metadata["status"] == "ANALYZED"
    assert metadata["raw_rows"] == 1


def test_preview_is_paginated_and_json_safe(client: TestClient) -> None:
    rows = [
        [2025, "PT.SST", "source.xlsx", "SST", index + 2, index, None, "Eman", None, "Perbaikan", "OK", None]
        for index in range(3)
    ]
    upload_payload = upload(client, workbook_bytes(rows=rows)).json()
    job_id = upload_payload["data"]["job_id"]

    response = client.get(
        f"/api/jobs/{job_id}/dataset/preview?page=2&page_size=2"
    )

    assert response.status_code == 200
    preview = response.json()["data"]
    assert preview["page"] == 2
    assert preview["total_rows"] == 3
    assert preview["total_pages"] == 2
    assert len(preview["items"]) == 1
    assert preview["items"][0]["Nama_User_Asli"] is None


def test_summary_uses_actual_dataset_values(client: TestClient) -> None:
    rows = [
        [2025, "PT.SST", "source.xlsx", "SST", 2, 1, None, "Eman", None, "Perbaikan", "OK", None],
        [2025, "PT.SST", "source.xlsx", "SST", 2, 1, None, "Eman", None, "Perbaikan", "OK", None],
    ]
    job_id = upload(client, workbook_bytes(rows=rows)).json()["data"]["job_id"]

    response = client.get(f"/api/jobs/{job_id}/dataset/summary")

    assert response.status_code == 200
    summary = response.json()["data"]
    assert summary["row_count"] == 2
    assert summary["column_count"] == 12
    assert summary["duplicate_rows"] == 1
    user_summary = next(
        item for item in summary["columns"] if item["name"] == "Nama_User_Asli"
    )
    assert user_summary["missing_count"] == 2
    assert user_summary["missing_percentage"] == 100.0


def test_summary_includes_domain_distributions_and_date_validity(
    client: TestClient,
) -> None:
    rows = [
        [2025, "PT.SST", "a.xlsx", "SST", 2, 1, datetime(2025, 1, 1), "Eman", " ", "Kerja", "OK", None],
        [2026, "PT. ASPAC", "b.xlsx", "ASPAC", 3, 2, datetime(2026, 4, 1), "Harry", "User", "Kerja", None, None],
        [2025, "PT.SST", "c.xlsx", "SST", 4, 3, None, None, None, None, None, None],
    ]
    job_id = upload(client, workbook_bytes(rows=rows)).json()["data"]["job_id"]

    response = client.get(f"/api/jobs/{job_id}/dataset/summary")

    assert response.status_code == 200
    summary = response.json()["data"]
    assert summary["operationally_empty_rows"] == 1
    assert summary["date_range"]["minimum"] == "2025-01-01"
    assert summary["date_range"]["maximum"] == "2026-04-01"
    assert summary["date_range"]["after_research_period"] == 1
    assert summary["date_range"]["invalid_or_missing"] == 1
    assert summary["distributions"]["year"] == [
        {"value": "2025", "count": 2},
        {"value": "2026", "count": 1},
    ]
    user_summary = next(
        item for item in summary["columns"] if item["name"] == "Nama_User_Asli"
    )
    assert user_summary["missing_count"] == 2


def test_preset_rejects_wrong_sheet_but_upload_allows_arbitrary_sheet(client: TestClient, tmp_path: Path) -> None:
    response = upload(client, workbook_bytes(sheet_name="Sheet1"))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"
    jobs_root = tmp_path / "storage" / "jobs"
    assert len(list(jobs_root.iterdir())) == 1


def test_upload_rejects_invalid_headers(client: TestClient) -> None:
    headers = list(get_settings().required_columns)
    headers[-1] = "Kolom_Salah"

    response = upload(client, workbook_bytes(headers=tuple(headers)))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"


def test_upload_rejects_non_xlsx(client: TestClient) -> None:
    response = upload(client, b"not an excel file", "dataset.csv")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"


def test_upload_rejects_empty_xlsx(client: TestClient) -> None:
    response = upload(client, b"")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"


def test_missing_job_uses_consistent_error_contract(client: TestClient) -> None:
    response = client.get("/api/jobs/not-a-real-job/dataset/summary")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "JOB_NOT_FOUND",
            "message": "Job 'not-a-real-job' tidak ditemukan.",
        },
    }


def test_dataset_summary_does_not_regress_cleaned_job_status(
    client: TestClient, tmp_path: Path
) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]
    assert client.post(f"/api/jobs/{job_id}/clean").status_code == 200

    response = client.get(f"/api/jobs/{job_id}/dataset/summary")

    assert response.status_code == 200
    metadata = json.loads(
        (tmp_path / "storage" / "jobs" / job_id / "config" / "job.json").read_text(
            "utf-8"
        )
    )
    assert metadata["status"] == "LABELED"


def test_job_overview_is_read_only_and_tracks_artifacts(client: TestClient, tmp_path: Path) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]
    job_path = tmp_path / "storage" / "jobs" / job_id
    metadata_path = job_path / "config" / "job.json"
    before = metadata_path.read_bytes()
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "ANALYZED"
    assert result["raw_rows"] == 1
    assert result["artifacts"]["raw"] is True
    assert result["artifacts"]["understanding"] is True
    assert result["artifacts"]["labeled"] is False
    assert metadata_path.read_bytes() == before
    assert client.post(f"/api/jobs/{job_id}/clean").status_code == 200
    cleaned_before = metadata_path.read_bytes()
    cleaned = client.get(f"/api/jobs/{job_id}").json()["data"]
    assert cleaned["status"] == "LABELED"
    assert cleaned["artifacts"]["cleaned"] is True
    assert cleaned["artifacts"]["labeled"] is True
    assert metadata_path.read_bytes() == cleaned_before


def test_job_overview_rejects_missing_or_invalid_job(client: TestClient) -> None:
    response = client.get("/api/jobs/not-a-real-job")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_upload_rejects_oversized_workbook_before_creating_job(client: TestClient, tmp_path: Path) -> None:
    response = upload(client, b"x" * (25 * 1024 * 1024 + 1))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"
    assert not (tmp_path / "storage" / "jobs").exists()


def test_upload_rejects_corrupted_xlsx_and_removes_partial_job(client: TestClient, tmp_path: Path) -> None:
    response = upload(client, b"corrupted workbook bytes", "corrupt.xlsx")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATASET"
    assert list((tmp_path / "storage" / "jobs").iterdir()) == []
