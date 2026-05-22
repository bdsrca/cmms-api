"""Persisted operator review records for extracted intake metadata."""

import json
import time
from copy import deepcopy
from typing import Any

from .db import db_execute, db_fetchone
from .intake_metadata import clean, clean_date

REVIEW_FIELDS = [
    ("submitted_by", "submission.submitted_by", ("submission", "submitted_by"), clean),
    ("submitted_email", "submission.submitted_email", ("submission", "submitted_email"), clean),
    ("submitted_phone", "submission.submitted_phone", ("submission", "submitted_phone"), clean),
    ("requested_due", "request.requested_due", ("request", "requested_due"), clean_date),
    ("building", "request.location.building", ("request", "location", "building"), clean),
    ("room", "request.location.room", ("request", "location", "room"), clean),
]


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, default=str)


def read_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def write_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    target = data
    for key in path[:-1]:
        nested = target.get(key)
        if not isinstance(nested, dict):
            nested = {}
            target[key] = nested
        target = nested
    target[path[-1]] = value


def corrected_fields(reviewed: dict[str, Any], extracted: dict[str, Any]) -> list[str]:
    return [field_path for _, field_path, path, _ in REVIEW_FIELDS if read_path(reviewed, path) != read_path(extracted, path)]


def apply_metadata_review_patch(extracted: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    reviewed = deepcopy(extracted)
    for patch_key, _, path, cleaner in REVIEW_FIELDS:
        if patch_key in patch:
            write_path(reviewed, path, cleaner(patch.get(patch_key)))
    reviewed["metadata_review"] = {
        "reviewed": True,
        "corrected_fields": corrected_fields(reviewed, extracted),
    }
    return reviewed


def save_extracted_metadata_review(run_id: str, submission: dict[str, Any], request: dict[str, Any]) -> None:
    timestamp = now_text()
    db_execute(
        """
        INSERT INTO intake_metadata_reviews
        (run_id, extracted_submission_json, extracted_request_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          extracted_submission_json = excluded.extracted_submission_json,
          extracted_request_json = excluded.extracted_request_json,
          updated_at = excluded.updated_at
        """,
        (run_id, json_text(submission), json_text(request), timestamp, timestamp),
    )


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def metadata_review_record(run_id: str) -> dict[str, Any] | None:
    row = db_fetchone("SELECT * FROM intake_metadata_reviews WHERE run_id = ?", (run_id,))
    if not row:
        return None
    record = dict(row)
    extracted = {
        "submission": parse_json_object(record.get("extracted_submission_json")),
        "request": parse_json_object(record.get("extracted_request_json")),
    }
    metadata_review = parse_json_object(record.get("metadata_review_json")) or {
        "reviewed": False,
        "corrected_fields": [],
    }
    return {
        "run_id": run_id,
        "extracted": extracted,
        "submission": parse_json_object(record.get("reviewed_submission_json")) or deepcopy(extracted["submission"]),
        "request": parse_json_object(record.get("reviewed_request_json")) or deepcopy(extracted["request"]),
        "metadata_review": metadata_review,
    }


def apply_saved_metadata_review(run_id: str, patch: dict[str, Any], reviewed_by_user_id: int | None) -> dict[str, Any] | None:
    record = metadata_review_record(run_id)
    if not record:
        return None
    reviewed = apply_metadata_review_patch(record["extracted"], patch)
    timestamp = now_text()
    db_execute(
        """
        UPDATE intake_metadata_reviews
        SET reviewed_submission_json = ?, reviewed_request_json = ?, metadata_review_json = ?,
            reviewed_by_user_id = ?, reviewed_at = ?, updated_at = ?
        WHERE run_id = ?
        """,
        (
            json_text(reviewed["submission"]),
            json_text(reviewed["request"]),
            json_text(reviewed["metadata_review"]),
            reviewed_by_user_id,
            timestamp,
            timestamp,
            run_id,
        ),
    )
    return {
        "run_id": run_id,
        "submission": reviewed["submission"],
        "request": reviewed["request"],
        "metadata_review": reviewed["metadata_review"],
    }
