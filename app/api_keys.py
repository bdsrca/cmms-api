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
        return auth

    incoming_hash = hash_text(x_api_key)
    row = db_fetchone(
        "SELECT key_id, name, enabled FROM api_keys WHERE key_hash = ?",
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
    return auth


def list_api_keys() -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT key_id, name, enabled, owner, created_at, last_used_at, usage_count FROM api_keys ORDER BY created_at DESC")
    return [dict(row) for row in rows]


def create_api_key(payload: Any, user: Any) -> dict[str, Any]:
    api_key = "cmms_" + secrets.token_urlsafe(32)
    key_id = "key_" + secrets.token_hex(4)
    db_execute(
        """
        INSERT INTO api_keys (key_id, name, key_hash, enabled, owner, created_at)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        (key_id, payload.name.strip(), hash_text(api_key), payload.owner, now_text()),
    )
    logger.info("api_key_created key_id=%s name=%s user=%s", key_id, payload.name.strip(), user.username)
    return {"key_id": key_id, "name": payload.name.strip(), "api_key": api_key, "enabled": True}


def patch_api_key(key_id: str, payload: Any) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM api_keys WHERE key_id = ?", (key_id,))
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    db_execute(
        "UPDATE api_keys SET name = ?, enabled = ? WHERE key_id = ?",
        (
            payload.name if payload.name is not None else row["name"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            key_id,
        ),
    )
    return {"status": "ok", "key_id": key_id}
