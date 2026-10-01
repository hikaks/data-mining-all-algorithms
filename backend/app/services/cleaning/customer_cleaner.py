from typing import Any

from app.services.cleaning.whitespace_cleaner import normalize_whitespace


def normalize_customer(value: Any, mapping: dict[str, str]) -> Any:
    normalized = normalize_whitespace(value)
    if normalized is None:
        return None
    return mapping.get(str(normalized), normalized)
