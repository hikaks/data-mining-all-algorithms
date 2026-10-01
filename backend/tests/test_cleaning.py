from datetime import date, datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pandas as pd

from app.services.cleaning.date_cleaner import normalize_date, validate_date_range
from app.services.cleaning.duplicate_cleaner import exact_duplicate_fingerprint
from app.services.cleaning.empty_row_cleaner import operationally_empty_mask
from app.services.cleaning.technician_cleaner import normalize_technicians
from tests.test_dataset import upload, workbook_bytes


def test_operationally_empty_requires_all_operational_fields_blank() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "Hari_Tgl_Asli": None,
                "Teknisi_Asli": " ",
                "Nama_User_Asli": None,
                "Keluhan_Solusi_Asli": "\n",
                "Status_Asli": None,
                "Yg_Mengetahui_Asli": None,
            },
            {
                "Hari_Tgl_Asli": None,
                "Teknisi_Asli": None,
                "Nama_User_Asli": None,
                "Keluhan_Solusi_Asli": "Masih ada informasi",
                "Status_Asli": None,
                "Yg_Mengetahui_Asli": None,
            },
        ]
    )

    assert operationally_empty_mask(dataframe).tolist() == [True, False]


def test_technician_normalization_maps_sorts_and_deduplicates() -> None:
    mapping = {"Harrry": "Harry", "Pak Victor": "Victor"}

    assert normalize_technicians("Pak Victor / Harrry / Victor", mapping) == "Harry | Victor"
    assert normalize_technicians("Abdull", mapping) == "Abdull"


def test_date_normalization_and_cutoff_validation() -> None:
    normalized, parsed, reason = normalize_date(datetime(2026, 4, 1))

    assert normalized == "2026-04-01"
    assert parsed is True
    assert reason is None
    assert validate_date_range(
        normalized, date(2023, 5, 3), date(2026, 3, 31)
    ) == (False, "AFTER_RESEARCH_PERIOD")


def test_exact_fingerprint_ignores_source_metadata() -> None:
    first = {
        "customer": "PT SST",
        "tanggal": "2025-01-10",
        "teknisi": "Arya | Eman",
        "nama_user": "User One",
        "keluhan_solusi": "Perbaikan printer",
        "sumber_file": "first.xlsx",
    }
    second = {**first, "sumber_file": "second.xlsx"}

    assert exact_duplicate_fingerprint(first) == exact_duplicate_fingerprint(second)


def test_cleaning_pipeline_is_auditable_and_preserves_raw(
    client: TestClient, tmp_path: Path
) -> None:
    rows = [
        [
            2025,
            "PT.SST",
            "first.xlsx",
            "SST",
            2,
            1,
            datetime(2025, 1, 10),
            "Eman/ Arya",
            " User\nOne ",
            " Perbaikan\nprinter ",
            " OK ",
            None,
        ],
        [
            2025,
            "PT.SST",
            "second.xlsx",
            "SST",
            7,
            99,
            datetime(2025, 1, 10),
            "Arya/ Eman",
            "User One",
            "Perbaikan printer",
            "OK",
            None,
        ],
        [
            2026,
            "PT. ASPAC",
            "third.xlsx",
            "ASPAC",
            3,
            2,
            datetime(2026, 4, 1),
            "Harrry",
            None,
            "Pemeriksaan lanjutan",
            None,
            "Supervisor",
        ],
        [2025, "PT.SST", "empty.xlsx", "SST", 8, 3, None, None, None, None, None, None],
    ]
    raw_content = workbook_bytes(rows=rows)
    job_id = upload(client, raw_content).json()["data"]["job_id"]
    raw_path = tmp_path / "storage" / "jobs" / job_id / "raw" / "dataset.xlsx"
    raw_before = raw_path.read_bytes()

    response = client.post(f"/api/jobs/{job_id}/clean")

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["rows_before"] == 4
    assert result["rows_after"] == 2
    assert result["empty_rows_removed"] == 1
    assert result["duplicates_removed"] == 1
    assert result["invalid_dates"] == 1
    assert raw_path.read_bytes() == raw_before == raw_content

    job_path = tmp_path / "storage" / "jobs" / job_id
    cleaned_path = job_path / "cleaned" / "dataset_cleaned.xlsx"
    report_path = job_path / "reports" / "cleaning_report.json"
    assert cleaned_path.is_file()
    assert report_path.is_file()

    cleaned = pd.read_excel(cleaned_path, sheet_name="DATA_CLEANED")
    assert len(cleaned) == 2
    assert cleaned.loc[0, "customer"] == "PT SST"
    assert cleaned.loc[0, "teknisi"] == "Arya | Eman"
    assert cleaned.loc[0, "nama_user"] == "User One"
    assert cleaned.loc[0, "keluhan_solusi"] == "Perbaikan printer"
    assert cleaned.loc[1, "customer"] == "PT ASPAC"
    assert cleaned.loc[1, "teknisi"] == "Harry"
    assert bool(cleaned.loc[1, "tanggal_valid"]) is False
    assert cleaned.loc[1, "tanggal_invalid_reason"] == "AFTER_RESEARCH_PERIOD"
    assert cleaned.loc[0, "keputusan_laporan"] == "SELESAI"
    assert pd.isna(cleaned.loc[1, "keputusan_laporan"])
    assert cleaned.loc[1, "labeling_status"] == "NEEDS_REVIEW"
    assert cleaned["keluhan"].isna().all()
    assert cleaned["solusi"].isna().all()

    report = json.loads(report_path.read_text("utf-8"))
    assert report["removed"] == {"empty_rows": 1, "duplicates": 1}
    assert report["duplicate_records"][0]["status"] == "EXACT_DUPLICATE_REMOVED"
    assert report["invalid_dates"][0]["reason"] == "AFTER_RESEARCH_PERIOD"
    assert report["near_duplicate_evaluation"]["status"] == "NOT_EVALUATED"
    assert any(operation["field"] == "customer" for operation in report["operations"])
    assert any(operation["field"] == "teknisi" for operation in report["operations"])

    metadata = json.loads((job_path / "config" / "job.json").read_text("utf-8"))
    assert metadata["status"] == "LABELED"
    assert metadata["cleaned_rows"] == 2


def test_cleaning_report_and_download_endpoints(client: TestClient) -> None:
    raw_content = workbook_bytes()
    job_id = upload(client, raw_content).json()["data"]["job_id"]

    missing_report = client.get(f"/api/jobs/{job_id}/cleaning-report")
    assert missing_report.status_code == 404
    assert missing_report.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"

    client.post(f"/api/jobs/{job_id}/clean")
    report = client.get(f"/api/jobs/{job_id}/cleaning-report")
    raw_download = client.get(f"/api/jobs/{job_id}/download/raw")
    cleaned_download = client.get(f"/api/jobs/{job_id}/download/cleaned")

    assert report.status_code == 200
    assert report.json()["data"]["rows_before"] == 1
    assert raw_download.status_code == 200
    assert raw_download.content == raw_content
    assert cleaned_download.status_code == 200
    assert cleaned_download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_cleaned_preview_and_audit_are_paginated(client: TestClient) -> None:
    rows = [
        [2025, "PT.SST", f"source-{index}.xlsx", "SST", index + 2, index, datetime(2025, 1, index + 1), "Eman", None, f"Kerja {index}", "OK", None]
        for index in range(3)
    ]
    job_id = upload(client, workbook_bytes(rows=rows)).json()["data"]["job_id"]

    missing_preview = client.get(f"/api/jobs/{job_id}/cleaned/preview")
    assert missing_preview.status_code == 404
    assert missing_preview.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"

    client.post(f"/api/jobs/{job_id}/clean")
    preview = client.get(
        f"/api/jobs/{job_id}/cleaned/preview?page=2&page_size=2"
    )
    audit = client.get(
        f"/api/jobs/{job_id}/cleaning-report/audit"
        "?section=incomplete_records&page=2&page_size=2"
    )

    assert preview.status_code == 200
    assert preview.json()["data"]["total_rows"] == 3
    assert preview.json()["data"]["total_pages"] == 2
    assert len(preview.json()["data"]["items"]) == 1
    assert audit.status_code == 200
    assert audit.json()["data"]["section"] == "incomplete_records"
    assert audit.json()["data"]["total_items"] == 3
    assert audit.json()["data"]["total_pages"] == 2
    assert len(audit.json()["data"]["items"]) == 1


def test_cleaning_audit_rejects_unknown_section(client: TestClient) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]
    client.post(f"/api/jobs/{job_id}/clean")

    response = client.get(
        f"/api/jobs/{job_id}/cleaning-report/audit?section=unknown"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_recleaning_is_deterministic(client: TestClient, tmp_path: Path) -> None:
    job_id = upload(client, workbook_bytes()).json()["data"]["job_id"]

    first = client.post(f"/api/jobs/{job_id}/clean")
    first_cleaned = pd.read_excel(
        tmp_path / "storage" / "jobs" / job_id / "cleaned" / "dataset_cleaned.xlsx"
    )
    second = client.post(f"/api/jobs/{job_id}/clean")
    second_cleaned = pd.read_excel(
        tmp_path / "storage" / "jobs" / job_id / "cleaned" / "dataset_cleaned.xlsx"
    )

    assert first.status_code == second.status_code == 200
    pd.testing.assert_frame_equal(first_cleaned, second_cleaned)
