from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from app.services.cleaning.whitespace_cleaner import is_blank


def normalize_date(value: Any) -> tuple[str | None, bool, str | None]:
    if is_blank(value):
        return None, False, "MISSING_DATE"

    parsed: pd.Timestamp | None = None
    if isinstance(value, pd.Timestamp):
        parsed = value
    elif isinstance(value, (datetime, date)):
        parsed = pd.Timestamp(value)
    elif isinstance(value, (int, float, np.integer, np.floating)):
        try:
            parsed = pd.Timestamp("1899-12-30") + pd.to_timedelta(float(value), unit="D")
        except (OverflowError, TypeError, ValueError):
            parsed = None
    elif isinstance(value, str):
        try:
            candidate = pd.to_datetime(value.strip(), errors="raise", dayfirst=True)
            parsed = pd.Timestamp(candidate)
        except (TypeError, ValueError):
            parsed = None

    if parsed is None or pd.isna(parsed):
        return None, False, "UNPARSEABLE_DATE"
    return parsed.date().isoformat(), True, None


def validate_date_range(
    normalized_date: str | None, start_date: date, cutoff_date: date
) -> tuple[bool, str | None]:
    if normalized_date is None:
        return False, "MISSING_OR_INVALID_DATE"
    parsed = date.fromisoformat(normalized_date)
    if parsed < start_date:
        return False, "BEFORE_RESEARCH_PERIOD"
    if parsed > cutoff_date:
        return False, "AFTER_RESEARCH_PERIOD"
    return True, None
