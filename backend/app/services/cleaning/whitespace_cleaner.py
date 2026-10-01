from typing import Any
import re

import pandas as pd


WHITESPACE_PATTERN = re.compile(r"\s+")


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and not value.strip()


def normalize_whitespace(value: Any) -> Any:
    if is_blank(value):
        return None
    if isinstance(value, str):
        return WHITESPACE_PATTERN.sub(" ", value).strip()
    return value


def comparable_text(value: Any) -> str:
    normalized = normalize_whitespace(value)
    return "" if normalized is None else str(normalized).casefold()
