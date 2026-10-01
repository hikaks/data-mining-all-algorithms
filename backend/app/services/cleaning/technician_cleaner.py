from typing import Any
import re

from app.services.cleaning.whitespace_cleaner import normalize_whitespace


TECHNICIAN_SEPARATOR = re.compile(r"\s*(?:/|\||;|,)\s*")


def normalize_technicians(value: Any, mapping: dict[str, str]) -> Any:
    normalized = normalize_whitespace(value)
    if normalized is None:
        return None

    technicians: dict[str, str] = {}
    for item in TECHNICIAN_SEPARATOR.split(str(normalized)):
        name = normalize_whitespace(item)
        if name is None:
            continue
        canonical = mapping.get(str(name), str(name))
        technicians.setdefault(canonical.casefold(), canonical)
    if not technicians:
        return None
    return " | ".join(sorted(technicians.values(), key=str.casefold))
