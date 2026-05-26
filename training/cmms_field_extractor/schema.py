"""Schema checks for CMMS field extractor training records."""

from __future__ import annotations

import json
from typing import Any


REQUIRED_ASSISTANT_KEYS = {
    "request_type",
    "building",
    "room",
    "asset_hint",
    "priority",
    "summary",
    "missing_fields",
    "human_review_recommended",
}

STRING_OR_NULL_KEYS = {"building", "room", "asset_hint", "priority", "summary"}
UNSAFE_CLAIMS = (
    "work order created",
    "created work order",
    "submitted work order",
    "sent email",
    "emailed",
)


def assistant_payload_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = REQUIRED_ASSISTANT_KEYS - set(payload)
    for key in sorted(missing):
        errors.append(f"assistant.{key}:missing")

    extra = set(payload) - REQUIRED_ASSISTANT_KEYS
    for key in sorted(extra):
        errors.append(f"assistant.extra:{key}")

    for key in STRING_OR_NULL_KEYS:
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"assistant.{key}:expected_string_or_null")

    if not isinstance(payload.get("request_type"), str):
        errors.append("assistant.request_type:expected_string")

    if not isinstance(payload.get("missing_fields"), list):
        errors.append("assistant.missing_fields:expected_list")

    if not isinstance(payload.get("human_review_recommended"), bool):
        errors.append("assistant.human_review_recommended:expected_bool")

    for key in ("summary",):
        value = payload.get(key)
        if isinstance(value, str) and any(claim in value.lower() for claim in UNSAFE_CLAIMS):
            errors.append(f"assistant.unsafe_claim:{key}")

    return errors


def validate_chat_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        return ["messages:expected_system_user_assistant"]

    expected_roles = ["system", "user", "assistant"]
    for index, role in enumerate(expected_roles):
        message = messages[index]
        if not isinstance(message, dict):
            errors.append(f"messages.{index}:expected_object")
            continue
        if message.get("role") != role:
            errors.append(f"messages.{index}.role:expected_{role}")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            errors.append(f"messages.{index}.content:expected_non_empty_string")

    assistant_content = messages[2].get("content") if isinstance(messages[2], dict) else None
    if isinstance(assistant_content, str):
        try:
            payload = json.loads(assistant_content)
        except json.JSONDecodeError:
            errors.append("assistant.content:invalid_json")
        else:
            if not isinstance(payload, dict):
                errors.append("assistant.content:expected_json_object")
            else:
                errors.extend(assistant_payload_errors(payload))

    return errors
