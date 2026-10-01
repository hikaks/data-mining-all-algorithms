from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from app.schemas.dataset import ColumnSummary, DatasetSummary
from app.services.cleaning.date_cleaner import normalize_date, validate_date_range
from app.services.cleaning.empty_row_cleaner import operationally_empty_mask
from app.services.cleaning.whitespace_cleaner import is_blank, normalize_whitespace


def build_summary(
    job_id: str,
    sheet_name: str,
    dataframe: pd.DataFrame,
    start_date: date,
    cutoff_date: date,
) -> DatasetSummary:
    row_count = len(dataframe)
    column_summaries: list[ColumnSummary] = []
    for column in dataframe.columns:
        missing_count = int(dataframe[column].map(is_blank).sum())
        column_summaries.append(
            ColumnSummary(
                name=str(column),
                dtype=str(dataframe[column].dtype),
                missing_count=missing_count,
                missing_percentage=round((missing_count / row_count) * 100, 2),
                non_missing_count=row_count - missing_count,
                unique_count=len(
                    {
                        str(normalized)
                        for value in dataframe[column]
                        if (normalized := normalize_whitespace(value)) is not None
                    }
                ),
            )
        )

    normalized_dates = [normalize_date(value)[0] for value in dataframe["Hari_Tgl_Asli"]]
    valid_parsed_dates = [value for value in normalized_dates if value is not None]
    before_period = 0
    after_period = 0
    invalid_or_missing = 0
    for normalized_date in normalized_dates:
        valid, reason = validate_date_range(normalized_date, start_date, cutoff_date)
        if valid:
            continue
        if reason == "BEFORE_RESEARCH_PERIOD":
            before_period += 1
        elif reason == "AFTER_RESEARCH_PERIOD":
            after_period += 1
        else:
            invalid_or_missing += 1

    return DatasetSummary(
        job_id=job_id,
        sheet_name=sheet_name,
        row_count=row_count,
        column_count=len(dataframe.columns),
        duplicate_rows=int(dataframe.duplicated().sum()),
        operationally_empty_rows=int(operationally_empty_mask(dataframe).sum()),
        date_range={
            "minimum": min(valid_parsed_dates) if valid_parsed_dates else None,
            "maximum": max(valid_parsed_dates) if valid_parsed_dates else None,
            "before_research_period": before_period,
            "after_research_period": after_period,
            "invalid_or_missing": invalid_or_missing,
            "research_start": start_date.isoformat(),
            "research_cutoff": cutoff_date.isoformat(),
        },
        distributions={
            "year": _distribution(dataframe["Tahun_Sumber"]),
            "customer": _distribution(dataframe["Customer_Asli"]),
            "technician": _distribution(dataframe["Teknisi_Asli"]),
            "status": _distribution(dataframe["Status_Asli"]),
        },
        columns=column_summaries,
        generated_at=datetime.now(timezone.utc),
    )


def summary_to_json(summary: DatasetSummary) -> dict[str, Any]:
    return summary.model_dump(mode="json")


def _distribution(series: pd.Series) -> list[dict[str, Any]]:
    normalized = series.map(normalize_whitespace)
    counts = normalized.map(lambda value: "<KOSONG>" if value is None else str(value)).value_counts()
    return [
        {"value": value, "count": int(count)}
        for value, count in counts.items()
    ]
