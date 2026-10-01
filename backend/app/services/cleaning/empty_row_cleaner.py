from typing import Any

import pandas as pd

from app.services.cleaning.whitespace_cleaner import is_blank


OPERATIONAL_COLUMNS = (
    "Hari_Tgl_Asli",
    "Teknisi_Asli",
    "Nama_User_Asli",
    "Keluhan_Solusi_Asli",
    "Status_Asli",
    "Yg_Mengetahui_Asli",
)


def operationally_empty_mask(dataframe: pd.DataFrame) -> pd.Series:
    return dataframe.loc[:, OPERATIONAL_COLUMNS].map(is_blank).all(axis=1)


def source_reference(row: pd.Series, source_row_number: int) -> dict[str, Any]:
    baris_sumber = None if is_blank(row["Baris_Sumber"]) else row["Baris_Sumber"]
    if hasattr(baris_sumber, "item"):
        baris_sumber = baris_sumber.item()
    return {
        "source_row_number": source_row_number,
        "sumber_file": None if is_blank(row["Sumber_File"]) else str(row["Sumber_File"]),
        "sumber_sheet": None if is_blank(row["Sumber_Sheet"]) else str(row["Sumber_Sheet"]),
        "baris_sumber": baris_sumber,
    }
