from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Any

import pandas as pd

from app.services.cleaning.customer_cleaner import normalize_customer
from app.services.cleaning.date_cleaner import normalize_date, validate_date_range
from app.services.cleaning.duplicate_cleaner import exact_duplicate_fingerprint
from app.services.cleaning.empty_row_cleaner import (
    OPERATIONAL_COLUMNS,
    operationally_empty_mask,
    source_reference,
)
from app.services.cleaning.missing_value_cleaner import missing_fields
from app.services.cleaning.technician_cleaner import normalize_technicians
from app.services.cleaning.whitespace_cleaner import (
    is_blank,
    normalize_whitespace,
)


@dataclass
class CleaningOutput:
    dataframe: pd.DataFrame
    report: dict[str, Any]


CLEANED_COLUMNS = (
    "record_id",
    "tahun_sumber",
    "customer_asli",
    "sumber_file",
    "sumber_sheet",
    "baris_sumber",
    "no_asli",
    "tanggal",
    "tanggal_valid",
    "tanggal_invalid_reason",
    "customer",
    "teknisi",
    "nama_user",
    "keluhan_solusi",
    "status",
    "yang_mengetahui",
    "keluhan",
    "solusi",
    "keputusan_laporan",
    "is_incomplete",
    "incomplete_fields",
    "duplicate_fingerprint",
)


def clean_dataset(
    dataframe: pd.DataFrame,
    job_id: str,
    customer_mapping: dict[str, str],
    technician_mapping: dict[str, str],
    start_date: date,
    cutoff_date: date,
) -> CleaningOutput:
    empty_mask = operationally_empty_mask(dataframe)
    empty_rows = dataframe.loc[empty_mask]
    source_rows = dataframe.loc[~empty_mask]

    operations: list[dict[str, Any]] = []
    invalid_dates: list[dict[str, Any]] = []
    incomplete_records: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    cleaned_records: list[dict[str, Any]] = []
    seen_fingerprints: dict[str, str] = {}
    normalization_counts = {
        "whitespace": 0,
        "customer": 0,
        "technician": 0,
        "date": 0,
    }

    for source_index, row in source_rows.iterrows():
        source_row_number = int(source_index) + 2
        record_id = _record_id(job_id, source_row_number)
        customer = normalize_customer(row["Customer_Asli"], customer_mapping)
        technician = normalize_technicians(row["Teknisi_Asli"], technician_mapping)
        normalized_date, parsed, parse_reason = normalize_date(row["Hari_Tgl_Asli"])
        date_valid, range_reason = validate_date_range(
            normalized_date, start_date, cutoff_date
        )
        invalid_reason = parse_reason or range_reason

        normalized_fields = {
            "nama_user": normalize_whitespace(row["Nama_User_Asli"]),
            "keluhan_solusi": normalize_whitespace(row["Keluhan_Solusi_Asli"]),
            "status": normalize_whitespace(row["Status_Asli"]),
            "yang_mengetahui": normalize_whitespace(row["Yg_Mengetahui_Asli"]),
        }
        record: dict[str, Any] = {
            "record_id": record_id,
            "tahun_sumber": row["Tahun_Sumber"],
            "customer_asli": normalize_whitespace(row["Customer_Asli"]),
            "sumber_file": normalize_whitespace(row["Sumber_File"]),
            "sumber_sheet": normalize_whitespace(row["Sumber_Sheet"]),
            "baris_sumber": row["Baris_Sumber"],
            "no_asli": row["No_Asli"],
            "tanggal": normalized_date,
            "tanggal_valid": date_valid,
            "tanggal_invalid_reason": invalid_reason,
            "customer": customer,
            "teknisi": technician,
            **normalized_fields,
            "keluhan": None,
            "solusi": None,
            "keputusan_laporan": None,
        }
        missing = missing_fields(record)
        record["is_incomplete"] = bool(missing)
        record["incomplete_fields"] = " | ".join(missing) if missing else None
        fingerprint = exact_duplicate_fingerprint(record)
        record["duplicate_fingerprint"] = fingerprint

        _audit_change(
            operations,
            normalization_counts,
            record_id,
            "customer",
            row["Customer_Asli"],
            customer,
            "CUSTOMER_MAPPING_OR_WHITESPACE_NORMALIZATION",
            "customer",
        )
        _audit_change(
            operations,
            normalization_counts,
            record_id,
            "teknisi",
            row["Teknisi_Asli"],
            technician,
            "TECHNICIAN_MAPPING_SORTING_OR_SEPARATOR_NORMALIZATION",
            "technician",
        )
        if parsed and normalized_date != str(row["Hari_Tgl_Asli"]):
            normalization_counts["date"] += 1
            operations.append(
                _operation(
                    record_id,
                    "tanggal",
                    row["Hari_Tgl_Asli"],
                    normalized_date,
                    "DATE_FORMAT_NORMALIZATION",
                )
            )

        for raw_field, cleaned_field in (
            ("Nama_User_Asli", "nama_user"),
            ("Keluhan_Solusi_Asli", "keluhan_solusi"),
            ("Status_Asli", "status"),
            ("Yg_Mengetahui_Asli", "yang_mengetahui"),
        ):
            old_value = row[raw_field]
            new_value = record[cleaned_field]
            if _changed(old_value, new_value):
                normalization_counts["whitespace"] += 1
                if cleaned_field == "status":
                    operations.append(
                        _operation(
                            record_id,
                            cleaned_field,
                            old_value,
                            new_value,
                            "WHITESPACE_NORMALIZATION",
                        )
                    )

        kept_record_id = seen_fingerprints.get(fingerprint)
        if kept_record_id is not None:
            duplicate_records.append(
                {
                    "record_id": record_id,
                    "kept_record_id": kept_record_id,
                    "fingerprint": fingerprint,
                    "status": "EXACT_DUPLICATE_REMOVED",
                }
            )
            continue
        seen_fingerprints[fingerprint] = record_id
        cleaned_records.append(record)
        if not date_valid:
            invalid_dates.append(
                {
                    "record_id": record_id,
                    "old_value": _safe_value(row["Hari_Tgl_Asli"]),
                    "normalized_value": normalized_date,
                    "reason": invalid_reason,
                }
            )
        if missing:
            incomplete_records.append(
                {"record_id": record_id, "missing_fields": missing}
            )

    missing_values = {
        field: sum(is_blank(record[field]) for record in cleaned_records)
        for field in (
            "tanggal",
            "customer",
            "teknisi",
            "nama_user",
            "keluhan_solusi",
            "status",
            "yang_mengetahui",
            "keputusan_laporan",
        )
    }
    report: dict[str, Any] = {
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows_before": len(dataframe),
        "rows_after": len(cleaned_records),
        "removed": {
            "empty_rows": int(empty_mask.sum()),
            "duplicates": len(duplicate_records),
        },
        "normalization": normalization_counts,
        "missing_values": missing_values,
        "invalid_dates": invalid_dates,
        "incomplete_records": incomplete_records,
        "duplicate_records": duplicate_records,
        "operations": operations,
        "removed_empty_records": [
            source_reference(row, int(index) + 2)
            for index, row in empty_rows.iterrows()
        ],
        "potential_duplicates": [],
        "near_duplicate_evaluation": {
            "status": "NOT_EVALUATED",
            "reason": "Metode dan similarity threshold belum disetujui.",
        },
        "decisions": {
            "missing_values": "Dipertahankan dan ditandai sebagai incomplete.",
            "invalid_dates": "Dipertahankan dan ditandai invalid tanpa koreksi otomatis.",
            "keluhan_solusi": "Tidak dipisah karena aturan pemisahan belum disetujui.",
            "target": "keputusan_laporan dibiarkan kosong sampai historical labeling tervalidasi.",
        },
    }
    return CleaningOutput(pd.DataFrame(cleaned_records, columns=CLEANED_COLUMNS), report)


def _record_id(job_id: str, source_row_number: int) -> str:
    digest = sha256(f"{job_id}:{source_row_number}".encode("utf-8")).hexdigest()[:20]
    return f"REC-{digest.upper()}"


def _safe_value(value: Any) -> Any:
    if is_blank(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value).isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _changed(old_value: Any, new_value: Any) -> bool:
    return _safe_value(old_value) != _safe_value(new_value)


def _operation(
    record_id: str, field: str, old_value: Any, new_value: Any, reason: str
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "field": field,
        "old_value": _safe_value(old_value),
        "new_value": _safe_value(new_value),
        "reason": reason,
    }


def _audit_change(
    operations: list[dict[str, Any]],
    counts: dict[str, int],
    record_id: str,
    field: str,
    old_value: Any,
    new_value: Any,
    reason: str,
    count_key: str,
) -> None:
    if _changed(old_value, new_value):
        counts[count_key] += 1
        operations.append(_operation(record_id, field, old_value, new_value, reason))
