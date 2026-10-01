from typing import Any

from app.services.cleaning.whitespace_cleaner import is_blank


CLEANED_OPERATIONAL_FIELDS = (
    "tanggal",
    "teknisi",
    "nama_user",
    "keluhan_solusi",
    "status",
    "yang_mengetahui",
)


def missing_fields(record: dict[str, Any]) -> list[str]:
    return [field for field in CLEANED_OPERATIONAL_FIELDS if is_blank(record[field])]
