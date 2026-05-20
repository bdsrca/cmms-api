"""Metadata-only logger for the showcase."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEYS = {"text", "body", "transcript", "image", "audio", "api_key", "token", "secret", "prompt", "summary", "asset_hint", "location_hint", "room"}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted[key] = f"[redacted:{stable_hash(value)}]"
        elif isinstance(value, dict):
            redacted[key] = redact_payload(value)
        else:
            redacted[key] = value
    return redacted


def build_event(*, endpoint: str, token_prefix: str, environment_code: str, status: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "token_prefix": token_prefix,
        "environment_code": environment_code,
        "status": status,
        "payload": redact_payload(payload),
        "payload_hash": stable_hash(payload),
    }
