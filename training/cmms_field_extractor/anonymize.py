"""Anonymization and normalization helpers for CMMS extractor training data."""

from __future__ import annotations

import json
import re
from typing import Any

from .schema import SUMMARY_MAX_CHARS, validate_chat_record


SYSTEM_PROMPT = (
    "Extract CMMS work request fields for a college/campus facilities environment. "
    "Do not predict building or room; those are input code fields merged by the API. "
    "Use exact CMMS code casing for request_type and priority, for example HVAC, General Maintenance, P3. "
    f"Keep summary concise, at most {SUMMARY_MAX_CHARS} characters. "
    "Return strict JSON only. "
    "Never claim a work order was created."
)


class SecretDetectedError(ValueError):
    """Raised when a training example contains data that must not be stored."""


SENSITIVE_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "url": re.compile(r"https?://\S+", re.IGNORECASE),
    "api_key": re.compile(r"\b(?:api[_-]?key|token|secret|sk-[a-z0-9_-]+)\b", re.IGNORECASE),
}

INPUT_CODE_FIELDS = {"building", "room"}


def reject_if_sensitive(text: str) -> None:
    for name, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(text):
            raise SecretDetectedError(f"sensitive_{name}_detected")


def _clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_summary(value: Any) -> str | None:
    cleaned = _clean_optional_string(" ".join(str(value).split()) if value is not None else None)
    if cleaned is None or len(cleaned) <= SUMMARY_MAX_CHARS:
        return cleaned
    clipped = cleaned[:SUMMARY_MAX_CHARS].rstrip()
    if " " in clipped:
        word_boundary = clipped.rsplit(" ", 1)[0].rstrip()
        if len(word_boundary) >= int(SUMMARY_MAX_CHARS * 0.75):
            clipped = word_boundary
    return clipped.rstrip(" ,;:-")


def _clean_missing_fields(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        field = str(item).strip()
        if field and field not in INPUT_CODE_FIELDS and field not in seen:
            seen.add(field)
            result.append(field)
    return result


def normalize_expected_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_type": str(payload.get("request_type", "")).strip(),
        "asset_hint": _clean_optional_string(payload.get("asset_hint")),
        "priority": _clean_optional_string(payload.get("priority")),
        "summary": _clean_summary(payload.get("summary")),
        "missing_fields": _clean_missing_fields(payload.get("missing_fields")),
        "human_review_recommended": bool(payload.get("human_review_recommended")),
    }


def build_chat_record(user_text: str, expected: dict[str, Any]) -> dict[str, Any]:
    reject_if_sensitive(user_text)
    normalized = normalize_expected_payload(expected)
    assistant_content = json.dumps(normalized, separators=(",", ":"))
    record = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text.strip()},
            {"role": "assistant", "content": assistant_content},
        ]
    }
    errors = validate_chat_record(record)
    if errors:
        raise ValueError(f"invalid_training_record:{errors}")
    return record
