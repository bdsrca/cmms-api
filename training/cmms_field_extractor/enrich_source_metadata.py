"""Build local CMMS training sidecar rows with source workbook metadata."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SOURCE_CLEAN_EXCLUDE_FLAGS = {
    "no_source_match",
    "source_request_type_conflict",
    "source_priority_conflict",
}

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from training.cmms_field_extractor.audit_source_failures import find_source_matches, load_work_order_rows
else:
    from .audit_source_failures import find_source_matches, load_work_order_rows


def load_job_type_request_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping = payload.get("request_type_map", {})
    if not isinstance(mapping, dict):
        raise ValueError("request_type_map:expected_object")
    return {str(key).strip(): str(value).strip() for key, value in mapping.items() if str(key).strip()}


def load_chat_records(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            record = json.loads(line)
            user_text = next(message["content"] for message in record["messages"] if message["role"] == "user")
            expected_text = next(message["content"] for message in record["messages"] if message["role"] == "assistant")
            records.append(
                {
                    "id": str(index),
                    "messages": record["messages"],
                    "user": user_text,
                    "expected": json.loads(expected_text),
                }
            )
    return records


def source_match_metadata(match: dict[str, str], job_type_request_map: dict[str, str]) -> dict[str, str | None]:
    job_type = str(match.get("job_type") or "").strip()
    return {
        "wo": str(match.get("wo") or "").strip(),
        "type": str(match.get("type") or "").strip(),
        "job_type": job_type,
        "source_request_type": job_type_request_map.get(job_type),
        "priority": str(match.get("priority") or "").strip(),
        "building": str(match.get("building") or "").strip(),
        "room": str(match.get("room") or "").strip(),
    }


def select_source_match(
    matches: list[dict[str, str | None]],
    expected: dict[str, Any],
) -> dict[str, str | None] | None:
    if not matches:
        return None
    expected_request_type = expected.get("request_type")
    expected_priority = expected.get("priority")
    for match in matches:
        if match.get("source_request_type") == expected_request_type and match.get("priority") == expected_priority:
            return match
    for match in matches:
        if match.get("source_request_type") == expected_request_type:
            return match
    return matches[0]


def source_review_flags(
    matches: list[dict[str, str | None]],
    expected: dict[str, Any],
) -> list[str]:
    if not matches:
        return ["no_source_match"]

    flags: list[str] = []
    if len(matches) > 1:
        flags.append("multiple_source_matches")

    job_types = {match.get("job_type") for match in matches if match.get("job_type")}
    if len(job_types) > 1:
        flags.append("multiple_source_job_types")

    priorities = {match.get("priority") for match in matches if match.get("priority")}
    if len(priorities) > 1:
        flags.append("multiple_source_priorities")

    expected_request_type = expected.get("request_type")
    mapped_types = {
        match.get("source_request_type")
        for match in matches
        if match.get("source_request_type")
    }
    if expected_request_type and any(mapped_type != expected_request_type for mapped_type in mapped_types):
        flags.append("source_request_type_conflict")

    expected_priority = expected.get("priority")
    if expected_priority and any(priority != expected_priority for priority in priorities):
        flags.append("source_priority_conflict")

    return flags


def is_source_clean_row(row: dict[str, Any], exclude_flags: set[str] | None = None) -> bool:
    blocked_flags = SOURCE_CLEAN_EXCLUDE_FLAGS if exclude_flags is None else exclude_flags
    review_flags = set(row.get("review_flags") or [])
    return not (review_flags & blocked_flags)


def build_source_metadata_row(
    *,
    chat_row: dict[str, Any],
    source_matches: list[dict[str, str]],
    job_type_request_map: dict[str, str],
) -> dict[str, Any]:
    expected = chat_row["expected"]
    matches = [source_match_metadata(match, job_type_request_map) for match in source_matches]
    selected = select_source_match(matches, expected)
    match_status = "unmatched" if not matches else "multiple" if len(matches) > 1 else "matched"
    return {
        "id": chat_row["id"],
        "messages": chat_row.get("messages"),
        "source_metadata": {
            "match_status": match_status,
            "match_count": len(matches),
            "selected": selected,
            "matches": matches,
        },
        "review_flags": source_review_flags(matches, expected),
    }


def build_source_metadata_rows(
    *,
    chat_rows: list[dict[str, Any]],
    work_orders: list[dict[str, str]],
    job_type_request_map: dict[str, str],
    source_match_limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chat_row in chat_rows:
        matches = find_source_matches(chat_row["user"], work_orders, source_match_limit)
        rows.append(
            build_source_metadata_row(
                chat_row=chat_row,
                source_matches=matches,
                job_type_request_map=job_type_request_map,
            )
        )
    return rows


def summarize_metadata_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row["source_metadata"]["match_status"] for row in rows)
    flag_counts: Counter[str] = Counter()
    selected_job_types: Counter[str] = Counter()
    selected_request_types: Counter[str] = Counter()
    for row in rows:
        flag_counts.update(row["review_flags"])
        selected = row["source_metadata"].get("selected") or {}
        if selected.get("job_type"):
            selected_job_types[str(selected["job_type"])] += 1
        if selected.get("source_request_type"):
            selected_request_types[str(selected["source_request_type"])] += 1
    return {
        "records": len(rows),
        "match_status": status_counts.most_common(),
        "review_flags": flag_counts.most_common(),
        "selected_job_types": selected_job_types.most_common(20),
        "selected_request_types": selected_request_types.most_common(20),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create local source-metadata sidecar JSONL for CMMS examples.")
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--workbook", type=Path, default=Path("data/training data.XLSX"))
    parser.add_argument(
        "--job-type-map",
        type=Path,
        default=Path("data/cmms_field_extractor/prepared/job_type_admin_mapping.json"),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-match-limit", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_source_metadata_rows(
        chat_rows=load_chat_records(args.input_jsonl, args.limit),
        work_orders=load_work_order_rows(args.workbook),
        job_type_request_map=load_job_type_request_map(args.job_type_map),
        source_match_limit=args.source_match_limit,
    )
    write_jsonl(args.output_jsonl, rows)
    summary = summarize_metadata_rows(rows)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
