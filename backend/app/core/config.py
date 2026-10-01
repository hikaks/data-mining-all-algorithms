from dataclasses import dataclass
from datetime import date
from functools import lru_cache
import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    app_name: str
    api_prefix: str
    storage_root: Path
    mapping_config_root: Path
    max_upload_bytes: int
    required_sheet: str
    required_columns: tuple[str, ...]
    default_page_size: int
    max_page_size: int
    cors_origins: tuple[str, ...]
    data_start_date: date
    data_cutoff_date: date


@lru_cache
def get_settings() -> Settings:
    root = _project_root()
    origins = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    return Settings(
        app_name="PT Maxkomp Random Forest Data Mining System",
        api_prefix="/api",
        storage_root=Path(os.getenv("STORAGE_ROOT", root / "storage")),
        mapping_config_root=Path(
            os.getenv("MAPPING_CONFIG_ROOT", root / "backend" / "config")
        ),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
        required_sheet="DATA_MENTAH",
        required_columns=(
            "Tahun_Sumber",
            "Customer_Asli",
            "Sumber_File",
            "Sumber_Sheet",
            "Baris_Sumber",
            "No_Asli",
            "Hari_Tgl_Asli",
            "Teknisi_Asli",
            "Nama_User_Asli",
            "Keluhan_Solusi_Asli",
            "Status_Asli",
            "Yg_Mengetahui_Asli",
        ),
        default_page_size=50,
        max_page_size=100,
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        data_start_date=date.fromisoformat(
            os.getenv("DATA_START_DATE", "2023-05-03")
        ),
        data_cutoff_date=date.fromisoformat(
            os.getenv("DATA_CUTOFF_DATE", "2026-03-31")
        ),
    )
