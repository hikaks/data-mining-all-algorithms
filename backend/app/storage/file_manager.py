import json
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


def write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary_path.open("wb") as file_handle:
            file_handle.write(content)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    write_bytes_atomic(path, encoded)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def append_json_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size:
        with path.open("rb") as existing:
            existing.seek(-1, os.SEEK_END)
            if existing.read(1) != b"\n":
                raise ValueError("JSONL tidak diakhiri newline; append dibatalkan.")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="") as file_handle:
        file_handle.write(encoded)
        file_handle.flush()
        os.fsync(file_handle.fileno())


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    if path.stat().st_size:
        with path.open("rb") as existing:
            existing.seek(-1, os.SEEK_END)
            if existing.read(1) != b"\n":
                raise ValueError("JSONL tidak diakhiri newline dan dianggap tidak lengkap.")
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSONL tidak valid pada baris {line_number}."
                ) from error
            if not isinstance(value, dict):
                raise ValueError(f"Event JSONL baris {line_number} bukan object.")
            events.append(value)
    return events


def write_excel_atomic(path: Path, dataframe: pd.DataFrame, sheet_name: str, *, literal_strings: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
    try:
        dataframe.to_excel(
            temporary_path, index=False, sheet_name=sheet_name, engine="openpyxl"
        )
        if literal_strings:
            from openpyxl import load_workbook
            workbook = load_workbook(temporary_path)
            for row in workbook[sheet_name]:
                for cell in row:
                    if cell.data_type == "f":
                        cell.data_type = "s"
            workbook.save(temporary_path)
            workbook.close()
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_joblib_atomic(path: Path, value: Any, compress: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
    try:
        joblib.dump(value, temporary_path, compress=compress)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
