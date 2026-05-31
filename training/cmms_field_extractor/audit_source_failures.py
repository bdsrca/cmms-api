"""Trace CMMS extractor failures back to source workbook rows.

The prepared JSONL records intentionally contain only chat messages, so this
utility uses work-order text matching to recover source workbook context for
locked-test failures without requiring pandas/openpyxl.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


SPREADSHEET_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MATCH_FIELDS = ("request_type", "priority", "summary")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def column_number(cell_reference: str) -> int:
    letters = "".join(character for character in cell_reference if character.isalpha())
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter.upper()) - 64
    return number - 1


def load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("a:si", SPREADSHEET_NS):
        texts = [
            text.text or ""
            for text in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        values.append("".join(texts))
    return values


def load_work_order_rows(workbook_path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = load_shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in sheet.findall("a:sheetData/a:row", SPREADSHEET_NS):
            values: list[str] = []
            for cell in row.findall("a:c", SPREADSHEET_NS):
                index = column_number(cell.attrib.get("r", "A1"))
                while len(values) <= index:
                    values.append("")
                raw_value = cell.find("a:v", SPREADSHEET_NS)
                value = raw_value.text if raw_value is not None else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                values[index] = value
            rows.append(values)

    header = rows[6]
    column = {name: index for index, name in enumerate(header)}
    required = ("W/O#", "Type", "Job Type", "Building", "Room", "Priority", "Work Description")
    missing = [name for name in required if name not in column]
    if missing:
        raise ValueError(f"source_workbook_missing_columns:{missing}")

    work_orders: list[dict[str, str]] = []
    for row in rows[7:]:
        description = row[column["Work Description"]] if column["Work Description"] < len(row) else ""
        if not str(description).strip():
            continue
        work_orders.append(
            {
                "wo": row[column["W/O#"]] if column["W/O#"] < len(row) else "",
                "type": row[column["Type"]] if column["Type"] < len(row) else "",
                "job_type": row[column["Job Type"]] if column["Job Type"] < len(row) else "",
                "building": row[column["Building"]] if column["Building"] < len(row) else "",
                "room": row[column["Room"]] if column["Room"] < len(row) else "",
                "priority": row[column["Priority"]] if column["Priority"] < len(row) else "",
                "description": str(description),
            }
        )
    return work_orders


def load_chat_rows(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            record = json.loads(line)
            user_text = next(message["content"] for message in record["messages"] if message["role"] == "user")
            expected_text = next(message["content"] for message in record["messages"] if message["role"] == "assistant")
            rows.append({"id": str(index), "user": user_text, "expected": json.loads(expected_text)})
    return rows


def load_prediction_rows(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            record = json.loads(line)
            rows.append({"id": record.get("id", str(index)), "prediction": json.loads(record["prediction"])})
    return rows


def find_source_matches(user_text: str, work_orders: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    normalized_user = normalize_text(user_text)
    if not normalized_user:
        return []
    scored_matches: list[tuple[int, int, dict[str, str]]] = []
    user_prefix = normalized_user[:80]
    for work_order in work_orders:
        description = normalize_text(work_order["description"])
        score = 0
        if normalized_user in description:
            score = 300 + len(normalized_user)
        elif user_prefix and len(user_prefix) >= 40 and user_prefix in description:
            score = 200 + len(user_prefix)
        elif len(description) >= 40 and description in normalized_user:
            score = 100 + len(description)
        if score:
            scored_matches.append((score, len(description), work_order))
    scored_matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored_matches[:limit]]


def build_failure_audit(
    *,
    locked_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    work_orders: list[dict[str, str]],
    source_match_limit: int,
) -> list[dict[str, Any]]:
    by_id = {str(row["id"]): row for row in prediction_rows}
    audit_rows: list[dict[str, Any]] = []
    for locked in locked_rows:
        prediction = by_id.get(locked["id"])
        if prediction is None:
            continue
        expected = locked["expected"]
        predicted = prediction["prediction"]
        mismatched = [field for field in MATCH_FIELDS if expected.get(field) != predicted.get(field)]
        if not mismatched:
            continue
        audit_rows.append(
            {
                "id": locked["id"],
                "mismatched_fields": mismatched,
                "expected": {field: expected.get(field) for field in MATCH_FIELDS},
                "predicted": {field: predicted.get(field) for field in MATCH_FIELDS},
                "user_excerpt": locked["user"][:240],
                "source_matches": [
                    {
                        "wo": match["wo"],
                        "type": match["type"],
                        "job_type": match["job_type"],
                        "priority": match["priority"],
                        "building": match["building"],
                        "room": match["room"],
                    }
                    for match in find_source_matches(locked["user"], work_orders, source_match_limit)
                ],
            }
        )
    return audit_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace locked-test prediction failures to source workbook rows.")
    parser.add_argument("--workbook", type=Path, default=Path("data/training data.XLSX"))
    parser.add_argument("--locked-test", type=Path, default=Path("data/cmms_field_extractor/locked_test.jsonl"))
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("data/cmms_field_extractor/prepared/semantic_phi4_v4_max256_postprocessed_locked_test_25_predictions.jsonl"),
    )
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--source-match-limit", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    work_orders = load_work_order_rows(args.workbook)
    locked_rows = load_chat_rows(args.locked_test, args.limit)
    prediction_rows = load_prediction_rows(args.predictions, args.limit)
    audit_rows = build_failure_audit(
        locked_rows=locked_rows,
        prediction_rows=prediction_rows,
        work_orders=work_orders,
        source_match_limit=args.source_match_limit,
    )
    print(json.dumps({"total_failures": len(audit_rows), "failures": audit_rows}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
