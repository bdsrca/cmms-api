"""Prompt version management and prompt rendering helpers."""

import json
import sqlite3
import time
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from .config import DEFAULT_PROMPT_VERSIONS, MODEL_NAME, SUPPORTED_PROMPT_ENDPOINTS
from .db import db_execute, db_fetchall, db_fetchone
from .prompt_promotions import active_prompt_for_endpoint, check_prompt_promotion_gate, record_prompt_promotion


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_default_prompt_versions() -> None:
    timestamp = now_text()
    for endpoint, spec in DEFAULT_PROMPT_VERSIONS.items():
        row = db_fetchone(
            "SELECT id FROM ai_prompt_versions WHERE endpoint = ? AND version = ?",
            (endpoint, spec["version"]),
        )
        if row:
            continue
        db_execute(
            """
            INSERT INTO ai_prompt_versions
            (endpoint, version, name, status, system_prompt, user_template, model, temperature, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                endpoint,
                spec["version"],
                spec["name"],
                spec["system_prompt"],
                spec["user_template"],
                MODEL_NAME,
                float(spec["temperature"]),
                timestamp,
                timestamp,
            ),
        )


def active_prompt_version(endpoint: str) -> sqlite3.Row:
    if endpoint not in SUPPORTED_PROMPT_ENDPOINTS:
        raise HTTPException(status_code=400, detail="Unsupported prompt endpoint")
    row = db_fetchone(
        "SELECT * FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (endpoint,),
    )
    if row:
        return row
    seed_default_prompt_versions()
    row = db_fetchone(
        "SELECT * FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (endpoint,),
    )
    if not row:
        raise HTTPException(status_code=500, detail=f"No active prompt configured for {endpoint}")
    return row


def prompt_version_by_id(prompt_id: int) -> sqlite3.Row:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return row


def prompt_row_for(endpoint: str, prompt_id: int | None = None) -> sqlite3.Row:
    if prompt_id is not None:
        row = prompt_version_by_id(prompt_id)
        if row["endpoint"] != endpoint:
            raise HTTPException(status_code=400, detail="Prompt endpoint does not match requested endpoint")
        return row
    return active_prompt_version(endpoint)


def render_prompt_template(template: str, context: dict[str, Any]) -> str:
    rendered = template
    for key, value in context.items():
        if isinstance(value, str):
            replacement = value
        else:
            replacement = json.dumps(value, ensure_ascii=False)
        rendered = rendered.replace("{{" + key + "}}", replacement)
    return rendered


def prompt_metadata(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "prompt_id": row["id"],
        "prompt_version": row["version"],
        "model": row["model"],
        "temperature": float(row["temperature"]),
    }


def prompt_messages(endpoint: str, context: dict[str, Any], prompt_id: int | None = None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    row = prompt_row_for(endpoint, prompt_id)
    system_prompt = render_prompt_template(row["system_prompt"], context)
    user_prompt = render_prompt_template(row["user_template"], context)
    return ([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], prompt_metadata(row))


def intake_prompt_messages(context: dict[str, Any], prompt_id: int | None = None) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    row = prompt_row_for("cmms-intake", prompt_id)
    try:
        parts = json.loads(row["system_prompt"])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Active cmms-intake prompt contains invalid JSON") from exc
    required = {"classifier", "field_extractor", "draft_generator"}
    if not required.issubset(parts):
        raise HTTPException(status_code=500, detail="Active cmms-intake prompt is missing required prompt parts")
    user_text = render_prompt_template(row["user_template"], context)
    messages = {
        name: [{"role": "system", "content": render_prompt_template(parts[name], context)}, {"role": "user", "content": user_text}]
        for name in required
    }
    return messages, prompt_metadata(row)


def active_prompt_info(endpoint: str) -> dict[str, Any]:
    row = active_prompt_version(endpoint)
    return {
        "endpoint": row["endpoint"],
        "version": row["version"],
        "name": row["name"],
        "status": row["status"],
        "model": row["model"],
        "temperature": row["temperature"],
        "updated_at": row["updated_at"],
    }


def list_prompt_versions() -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_prompt_versions ORDER BY endpoint, updated_at DESC")
    return [dict(row) for row in rows]


def list_prompt_versions_for_endpoint(endpoint: str) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_prompt_versions WHERE endpoint = ? ORDER BY updated_at DESC", (endpoint,))
    return [dict(row) for row in rows]


def create_prompt_version(payload: Any, user: Any) -> dict[str, Any]:
    if payload.endpoint not in SUPPORTED_PROMPT_ENDPOINTS:
        raise HTTPException(status_code=400, detail="Unsupported prompt endpoint")
    if payload.status == "active":
        raise HTTPException(status_code=400, detail="Create prompt versions as draft, then use the promotion gate to activate")
    timestamp = now_text()
    try:
        db_execute(
            """
            INSERT INTO ai_prompt_versions
            (endpoint, version, name, status, system_prompt, user_template, model, temperature, created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.endpoint,
                payload.version,
                payload.name,
                payload.status,
                payload.system_prompt,
                payload.user_template,
                payload.model,
                payload.temperature,
                timestamp,
                timestamp,
                user.user_id,
                user.user_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Prompt endpoint/version already exists") from exc
    row = db_fetchone("SELECT id FROM ai_prompt_versions WHERE endpoint = ? AND version = ?", (payload.endpoint, payload.version))
    return {"status": "ok", "prompt_id": row["id"] if row else None}


def patch_prompt_version(prompt_id: int, payload: Any, user: Any) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    if row["status"] == "archived":
        raise HTTPException(status_code=400, detail="Archived prompts cannot be edited")
    db_execute(
        """
        UPDATE ai_prompt_versions
        SET name = ?, system_prompt = ?, user_template = ?, model = ?, temperature = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            payload.system_prompt if payload.system_prompt is not None else row["system_prompt"],
            payload.user_template if payload.user_template is not None else row["user_template"],
            payload.model if payload.model is not None else row["model"],
            payload.temperature if payload.temperature is not None else row["temperature"],
            now_text(),
            user.user_id,
            prompt_id,
        ),
    )
    return {"status": "ok", "prompt_id": prompt_id}


def activate_prompt_version(prompt_id: int, payload: Any | None, user: Any, activation_request_factory: Callable[[], Any]) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    if row["status"] == "archived":
        raise HTTPException(status_code=400, detail="Archived prompts cannot be activated")
    activation = payload or activation_request_factory()
    gate = check_prompt_promotion_gate(prompt_id, activation.comparison_id)
    gate_status = gate["gate_status"]
    override_used = False
    override_reason = None
    if not gate["allowed"]:
        if not activation.override:
            raise HTTPException(status_code=409, detail=gate)
        override_reason = (activation.override_reason or "").strip()
        if not override_reason:
            raise HTTPException(status_code=400, detail="override_reason is required when override is true")
        gate_status = "overridden"
        override_used = True
    timestamp = now_text()
    previous = active_prompt_for_endpoint(row["endpoint"])
    previous_prompt_id = previous["id"] if previous else None
    db_execute("UPDATE ai_prompt_versions SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, row["endpoint"]))
    db_execute("UPDATE ai_prompt_versions SET status = 'active', updated_at = ?, updated_by = ? WHERE id = ?", (timestamp, user.user_id, prompt_id))
    promotion_id = record_prompt_promotion(
        row["endpoint"],
        previous_prompt_id,
        prompt_id,
        activation.comparison_id,
        gate_status,
        override_used,
        override_reason,
        user.user_id,
        gate.get("summary") or {},
    )
    return {"status": "ok", "prompt_id": prompt_id, "promotion_id": promotion_id, "gate": gate | {"gate_status": gate_status, "override_used": override_used}}


def archive_prompt_version(prompt_id: int, user: Any) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    if row["status"] == "active":
        active_count = db_fetchone("SELECT COUNT(*) AS count FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active'", (row["endpoint"],))
        if active_count and active_count["count"] <= 1:
            raise HTTPException(status_code=400, detail="Cannot archive the only active prompt for an endpoint")
    db_execute("UPDATE ai_prompt_versions SET status = 'archived', updated_at = ?, updated_by = ? WHERE id = ?", (now_text(), user.user_id, prompt_id))
    return {"status": "ok", "prompt_id": prompt_id}


async def test_prompt_version(
    prompt_id: int,
    payload: Any,
    *,
    allowed_request_types: set[str],
    get_environment_values: Callable[[str], dict[str, list[str]]],
    call_ollama: Callable[..., Awaitable[str]],
) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    values = get_environment_values(payload.environment_code) if payload.environment_code else {"buildings": [], "priorities": ["NORMAL"]}
    context = {
        "text": payload.text,
        "allowed_request_types": sorted(allowed_request_types),
        "valid_buildings": values.get("buildings") or [],
        "valid_priorities": values.get("priorities") or ["NORMAL"],
    }
    endpoint = row["endpoint"]
    if endpoint == "cmms-intake":
        try:
            parts = json.loads(row["system_prompt"])
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Prompt system_prompt must be JSON for cmms-intake") from exc
        messages = [{"role": "system", "content": render_prompt_template(parts.get("field_extractor", ""), context)}, {"role": "user", "content": render_prompt_template(row["user_template"], context)}]
    else:
        messages = [{"role": "system", "content": render_prompt_template(row["system_prompt"], context)}, {"role": "user", "content": render_prompt_template(row["user_template"], context)}]
    output = await call_ollama(messages, temperature=float(row["temperature"]), model=row["model"])
    return {
        "status": "ok",
        "prompt_id": prompt_id,
        "endpoint": endpoint,
        "version": row["version"],
        "model": row["model"],
        "temperature": row["temperature"],
        "output": output,
    }
