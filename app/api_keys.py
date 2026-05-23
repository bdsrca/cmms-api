"""API key hashing, verification, creation, and usage tracking."""

import json
import logging
import os
import secrets
import time
from typing import Any

from fastapi import Header, HTTPException, Request

from .db import API_KEYS_JSON, db_execute, db_fetchall, db_fetchone
from .security import AuthContext, hash_text


logger = logging.getLogger("local-cmms-llm-api")

ALLOWED_AI_ENDPOINTS = {
    "summarize-work-order",
    "extract-work-order-fields",
    "cmms-intake",
    "intake/email",
    "cmms-assistant",
}


def normalize_scope_list(values: Any) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def normalize_allowed_endpoints(values: Any) -> list[str]:
    endpoints = normalize_scope_list(values)
    for endpoint in endpoints:
        if endpoint not in ALLOWED_AI_ENDPOINTS:
            raise HTTPException(status_code=422, detail=f"Unsupported API key endpoint scope: {endpoint}")
    return endpoints


def normalize_allowed_environments(values: Any) -> list[str]:
    normalized: list[str] = []
    for value in normalize_scope_list(values):
        environment_code = value.upper()
        if environment_code not in normalized:
            normalized.append(environment_code)
    return normalized


def scope_json(values: Any, *, environment: bool = False, endpoint: bool = False) -> str:
    if endpoint:
        normalized = normalize_allowed_endpoints(values)
    elif environment:
        normalized = normalize_allowed_environments(values)
    else:
        normalized = normalize_scope_list(values)
    return json.dumps(normalized)


def parse_scope_json(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return normalize_scope_list(data)


def parse_environment_scope_json(value: str | None) -> list[str]:
    return normalize_allowed_environments(parse_scope_json(value))


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def migrate_json_api_keys() -> None:
    if not API_KEYS_JSON.exists():
        return
    try:
        data = json.loads(API_KEYS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("api_keys_json_migration skipped=invalid_json")
        return
    for record in data.get("keys", []):
        if not record.get("key_id") or not record.get("key_hash"):
            continue
        db_execute(
            """
            INSERT OR IGNORE INTO api_keys
            (key_id, name, key_hash, enabled, owner, created_at, last_used_at, usage_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["key_id"],
                record.get("name") or record["key_id"],
                record["key_hash"],
                1 if record.get("enabled", True) else 0,
                record.get("owner"),
                record.get("created_at") or now_text(),
                record.get("last_used_at"),
                int(record.get("usage_count") or 0),
            ),
        )


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> AuthContext:
    expected_key = os.getenv("LLM_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="LLM_API_KEY environment variable is not set")
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if secrets.compare_digest(x_api_key, expected_key):
        auth = AuthContext(key_id="env-admin", name="Environment admin key", is_admin=True, source="env")
        request.state.api_key_id = auth.key_id
        request.state.api_key_name = auth.name
        request.state.allowed_endpoints = []
        request.state.allowed_environments = []
        return auth

    incoming_hash = hash_text(x_api_key)
    row = db_fetchone(
        """
        SELECT key_id, name, enabled, allowed_endpoints_json, allowed_environments_json
        FROM api_keys
        WHERE key_hash = ?
        """,
        (incoming_hash,),
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if not row["enabled"]:
        raise HTTPException(status_code=401, detail="API key is disabled")
    db_execute(
        "UPDATE api_keys SET usage_count = usage_count + 1, last_used_at = ? WHERE key_id = ?",
        (now_text(), row["key_id"]),
    )
    auth = AuthContext(key_id=row["key_id"], name=row["name"], is_admin=False, source="generated")
    request.state.api_key_id = auth.key_id
    request.state.api_key_name = auth.name
    request.state.allowed_endpoints = parse_scope_json(row["allowed_endpoints_json"])
    request.state.allowed_environments = parse_environment_scope_json(row["allowed_environments_json"])
    return auth


def enforce_api_key_scope(request: Request, endpoint: str, environment_code: str | None = None) -> None:
    allowed_endpoints = normalize_scope_list(getattr(request.state, "allowed_endpoints", []))
    allowed_environments = normalize_scope_list(getattr(request.state, "allowed_environments", []))
    if allowed_endpoints and endpoint not in allowed_endpoints:
        raise HTTPException(status_code=403, detail=f"API key is not allowed to call endpoint: {endpoint}")
    if environment_code and allowed_environments and environment_code.upper() not in allowed_environments:
        raise HTTPException(status_code=403, detail=f"API key is not allowed to use environment: {environment_code}")


def public_api_key_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["enabled"] = bool(data.get("enabled"))
    data["allowed_endpoints"] = parse_scope_json(data.pop("allowed_endpoints_json", None))
    data["allowed_environments"] = parse_environment_scope_json(data.pop("allowed_environments_json", None))
    data.pop("key_hash", None)
    return data


def list_api_keys() -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT key_id, name, enabled, owner, created_at, last_used_at, usage_count,
               allowed_endpoints_json, allowed_environments_json
        FROM api_keys
        ORDER BY created_at DESC
        """
    )
    return [public_api_key_row(row) for row in rows]


def create_api_key(payload: Any, user: Any) -> dict[str, Any]:
    api_key = "cmms_" + secrets.token_urlsafe(32)
    key_id = "key_" + secrets.token_hex(4)
    db_execute(
        """
        INSERT INTO api_keys
        (key_id, name, key_hash, enabled, owner, created_at, allowed_endpoints_json, allowed_environments_json)
        VALUES (?, ?, ?, 1, ?, ?, ?, ?)
        """,
        (
            key_id,
            payload.name.strip(),
            hash_text(api_key),
            payload.owner,
            now_text(),
            scope_json(getattr(payload, "allowed_endpoints", None), endpoint=True),
            scope_json(getattr(payload, "allowed_environments", None), environment=True),
        ),
    )
    logger.info("api_key_created key_id=%s name=%s user=%s", key_id, payload.name.strip(), user.username)
    return {
        "key_id": key_id,
        "name": payload.name.strip(),
        "api_key": api_key,
        "enabled": True,
        "allowed_endpoints": normalize_allowed_endpoints(getattr(payload, "allowed_endpoints", None)),
        "allowed_environments": normalize_allowed_environments(getattr(payload, "allowed_environments", None)),
    }


def patch_api_key(key_id: str, payload: Any) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM api_keys WHERE key_id = ?", (key_id,))
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    allowed_endpoints = (
        scope_json(getattr(payload, "allowed_endpoints"), endpoint=True)
        if getattr(payload, "allowed_endpoints", None) is not None
        else row["allowed_endpoints_json"]
    )
    allowed_environments = (
        scope_json(getattr(payload, "allowed_environments"), environment=True)
        if getattr(payload, "allowed_environments", None) is not None
        else row["allowed_environments_json"]
    )
    db_execute(
        """
        UPDATE api_keys
        SET name = ?, enabled = ?, allowed_endpoints_json = ?, allowed_environments_json = ?
        WHERE key_id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            allowed_endpoints,
            allowed_environments,
            key_id,
        ),
    )
    return {"status": "ok", "key_id": key_id}
