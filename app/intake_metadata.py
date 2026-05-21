"""Deterministic CMMS intake metadata helpers."""

import time
from typing import Any, Callable


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def clean_location(value: Any, fields: dict[str, Any]) -> tuple[dict[str, str | None], bool]:
    location = clean_mapping(value)
    explicit_building = clean(location.get("building"))
    explicit_room = clean(location.get("room"))
    field_building = clean(fields.get("building"))
    field_room = clean(fields.get("room"))
    merged = {
        "building": explicit_building or field_building,
        "room": explicit_room or field_room,
        "area": clean(location.get("area")),
        "raw": clean(location.get("raw")),
    }
    conflict = bool(
        (explicit_building and field_building and explicit_building != field_building)
        or (explicit_room and field_room and explicit_room != field_room)
    )
    return merged, conflict


def build_intake_metadata(
    *,
    source: str | None,
    fields: dict[str, Any],
    submission: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    submitted_email: str | None = None,
    now_func: Callable[[], str] = now_text,
) -> dict[str, Any]:
    submission_data = clean_mapping(submission)
    request_data = clean_mapping(request)
    source_name = clean(source) or clean(submission_data.get("submitted_method")) or "manual"
    submitted_at = clean(submission_data.get("submitted_at")) or now_func()
    location, location_conflict = clean_location(request_data.get("location"), fields)
    return {
        "submission": {
            "submitted_by": clean(submission_data.get("submitted_by")),
            "submitted_email": clean(submission_data.get("submitted_email")) or clean(submitted_email),
            "submitted_phone": clean(submission_data.get("submitted_phone")),
            "submitted_at": submitted_at,
            "submitted_method": source_name,
        },
        "request": {
            "requested_due_at": clean(request_data.get("requested_due_at")),
            "location": location,
            "location_conflict": location_conflict,
        },
    }
