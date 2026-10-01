from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException

from app.core.exceptions import InvalidDatasetError
from app.core.dataset_contract import INPUT_LABEL_COLUMNS


def inspect_workbook(
    path: Path, required_sheet: str, required_columns: tuple[str, ...]
) -> pd.DataFrame:
    try:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            if required_sheet not in workbook.sheet_names:
                available = ", ".join(workbook.sheet_names) or "tidak ada"
                raise InvalidDatasetError(
                    f"Sheet wajib '{required_sheet}' tidak ditemukan. "
                    f"Sheet tersedia: {available}."
                )
            dataframe = workbook.parse(required_sheet, dtype=object)
    except InvalidDatasetError:
        raise
    except (InvalidFileException, OSError, ValueError, KeyError, TypeError) as error:
        raise InvalidDatasetError(
            "Workbook tidak dapat dibaca atau format file rusak."
        ) from error

    columns = [str(column).strip() for column in dataframe.columns]
    dataframe.columns = columns
    missing = [column for column in required_columns if column not in columns]
    allowed = (*required_columns, *INPUT_LABEL_COLUMNS)
    unexpected = [column for column in columns if column not in allowed]
    if missing or unexpected or columns not in [list(required_columns), list(allowed)]:
        details: list[str] = []
        if missing:
            details.append(f"kolom wajib tidak ditemukan: {', '.join(missing)}")
        if unexpected:
            details.append(f"kolom tidak dikenal: {', '.join(unexpected)}")
        if not missing and not unexpected:
            details.append("urutan kolom tidak sesuai kontrak")
        raise InvalidDatasetError("Header dataset tidak valid; " + "; ".join(details) + ".")
    if dataframe.empty:
        raise InvalidDatasetError("Dataset tidak memiliki baris data.")
    return dataframe


def to_json_safe(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def dataframe_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: to_json_safe(value) for column, value in row.items()}
        for row in dataframe.to_dict(orient="records")
    ]
