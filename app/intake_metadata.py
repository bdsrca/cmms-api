"""Deterministic CMMS intake metadata helpers."""

import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

WEEKDAY_INDEXES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_phone(value: Any) -> str | None:
    phone = clean(value)
    return phone.rstrip(".,;") if phone else None


def clean_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def unreviewed_metadata_review() -> dict[str, Any]:
    return {"reviewed": False, "corrected_fields": []}


def clean_date(value: Any) -> str | None:
    text = clean(value)
    if not text:
        return None
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[T ].*)?", text)
    if not match:
        return None
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return None
    return match.group(1)


def current_datetime(now_func: Callable[[], str]) -> datetime:
    try:
        return datetime.fromisoformat(now_func().replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def end_of_week_date(now_func: Callable[[], str]) -> str:
    today = current_datetime(now_func).date()
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    return friday.isoformat()


def next_weekday_date(weekday_name: str, now_func: Callable[[], str]) -> str:
    today = current_datetime(now_func).date()
    weekday = WEEKDAY_INDEXES[weekday_name.lower()]
    days_until = (weekday - today.weekday()) % 7
    if days_until == 0:
        days_until = 7
    return (today + timedelta(days=days_until)).isoformat()


def end_of_month_date(now_func: Callable[[], str]) -> str:
    today = current_datetime(now_func).date()
    next_month = today.replace(day=28) + timedelta(days=4)
    return (next_month.replace(day=1) - timedelta(days=1)).isoformat()


def extract_metadata_from_text(
    text: str,
    *,
    now_func: Callable[[], str] = now_text,
) -> dict[str, Any]:
    name_match = re.search(
        r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{0,159}?)(?=,|;|\.\s|\bphone\b|\bemail\b|$)",
        text,
        re.IGNORECASE,
    )
    intro_name_match = re.search(
        r"\bthis is\s+([A-Za-z][A-Za-z .'-]{0,159}?)(?=,|;|\.\s|$)",
        text,
        re.IGNORECASE,
    )
    phone_match = re.search(
        r"\b(?:phone(?: number)?|telephone|mobile)\s*(?:is|:)?\s*([+()0-9][0-9+() .-]{2,79})",
        text,
        re.IGNORECASE,
    )
    call_phone_match = re.search(
        r"\bcall me at\s*([+()0-9][0-9+() .-]{2,79})",
        text,
        re.IGNORECASE,
    )
    header_email_match = re.search(
        r"(?im)^from:\s*[^<\n]*<?([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})>?",
        text,
    )
    inline_email_match = re.search(
        r"\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b",
        text,
        re.IGNORECASE,
    )
    location_match = re.search(
        r"\b([A-Z][A-Z0-9-]{1,15})\s+(?:room|rm|suite)\s*([A-Z0-9-]+)\b",
        text,
        re.IGNORECASE,
    )
    compact_location_match = re.search(
        r"\b([A-Z]{2,15})\s+([0-9][A-Z0-9-]{0,15})\b",
        text,
    )
    end_week_match = re.search(
        r"\bby\s+(?:the\s+)?end\s+of\s+(?:this\s+)?week\b",
        text,
        re.IGNORECASE,
    )
    tomorrow_match = re.search(r"\bby\s+tomorrow\b", text, re.IGNORECASE)
    next_weekday_match = re.search(
        r"\bby\s+next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
        re.IGNORECASE,
    )
    end_month_match = re.search(
        r"\bby\s+(?:the\s+)?end\s+of\s+(?:this\s+)?month\b",
        text,
        re.IGNORECASE,
    )
    iso_due_match = re.search(
        r"\b(?:by|due(?:\s+on)?|needed(?:\s+by)?|done\s+by)\s+(20\d{2}-\d{2}-\d{2})\b",
        text,
        re.IGNORECASE,
    )

    location_match = location_match or compact_location_match
    location: dict[str, str | None] | None = None
    if location_match:
        location = {
            "building": clean(location_match.group(1)),
            "room": clean(location_match.group(2)),
            "area": None,
            "raw": clean(location_match.group(0)),
        }

    requested_due = clean_date(iso_due_match.group(1)) if iso_due_match else None
    requested_due_raw = clean(iso_due_match.group(0)) if iso_due_match else None
    if not requested_due and end_week_match:
        requested_due = end_of_week_date(now_func)
        requested_due_raw = clean(end_week_match.group(0))
    if not requested_due and tomorrow_match:
        requested_due = (current_datetime(now_func).date() + timedelta(days=1)).isoformat()
        requested_due_raw = clean(tomorrow_match.group(0))
    if not requested_due and next_weekday_match:
        requested_due = next_weekday_date(next_weekday_match.group(1), now_func)
        requested_due_raw = clean(next_weekday_match.group(0))
    if not requested_due and end_month_match:
        requested_due = end_of_month_date(now_func)
        requested_due_raw = clean(end_month_match.group(0))

    email_match = header_email_match or inline_email_match
    name_match = name_match or intro_name_match
    phone_match = phone_match or call_phone_match
    return {
        "submission": {
            "submitted_by": clean(name_match.group(1)) if name_match else None,
            "submitted_email": clean(email_match.group(1)) if email_match else None,
            "submitted_phone": clean_phone(phone_match.group(1)) if phone_match else None,
        },
        "request": {
            "requested_due": requested_due,
            "requested_due_raw": requested_due_raw,
            "location": location,
        },
    }


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
    extracted: dict[str, Any] | None = None,
    submitted_email: str | None = None,
    now_func: Callable[[], str] = now_text,
) -> dict[str, Any]:
    extracted_data = clean_mapping(extracted)
    submission_data = clean_mapping(extracted_data.get("submission"))
    request_data = clean_mapping(extracted_data.get("request"))
    source_name = clean(source) or clean(submission_data.get("submitted_method")) or "manual"
    submitted_at = clean(submission_data.get("submitted_at")) or now_func()
    location, location_conflict = clean_location(request_data.get("location"), fields)
    return {
        "submission": {
            "submitted_by": clean(submission_data.get("submitted_by")),
            "submitted_email": clean(submission_data.get("submitted_email")) or clean(submitted_email),
            "submitted_phone": clean_phone(submission_data.get("submitted_phone")),
            "submitted_at": submitted_at,
            "submitted_method": source_name,
        },
        "request": {
            "requested_due": clean_date(request_data.get("requested_due")),
            "requested_due_raw": clean(request_data.get("requested_due_raw")),
            "location": location,
            "location_conflict": location_conflict,
        },
    }
