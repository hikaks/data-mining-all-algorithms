from hashlib import sha256
from typing import Any

from app.services.cleaning.whitespace_cleaner import comparable_text


FINGERPRINT_FIELDS = (
    "customer",
    "tanggal",
    "teknisi",
    "nama_user",
    "keluhan_solusi",
)


def exact_duplicate_fingerprint(record: dict[str, Any]) -> str:
    normalized = "\x1f".join(comparable_text(record[field]) for field in FINGERPRINT_FIELDS)
    return sha256(normalized.encode("utf-8")).hexdigest()
