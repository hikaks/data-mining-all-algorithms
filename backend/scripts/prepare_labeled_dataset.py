"""Extract auditable portable labels as JSON for the spreadsheet builder.

The source workbook is read-only. XLSX authoring is handled by the builder.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.core.dataset_contract import INPUT_LABEL_COLUMNS
from app.services.dataset_labels import identify_raw_row
from app.utils.excel import inspect_workbook


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    dataframe = inspect_workbook(args.source, settings.required_sheet, settings.required_columns)
    if list(dataframe.columns) != list(settings.required_columns):
        raise ValueError("Expected immutable raw source, not an already labeled workbook.")
    timestamp = datetime.now(timezone.utc).isoformat()
    labels = [identify_raw_row(row, timestamp) for _, row in dataframe.iterrows()]
    counts = dict(Counter(row["keputusan_laporan"] or "NEEDS_REVIEW" for row in labels))
    payload = {
        "source_sha256": sha256(args.source.read_bytes()).hexdigest(),
        "source_filename": args.source.name,
        "columns": list(INPUT_LABEL_COLUMNS),
        "rows": [[row[name] for name in INPUT_LABEL_COLUMNS] for row in labels],
        "row_count": len(labels), "decision_counts": counts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}))


if __name__ == "__main__":
    main()
