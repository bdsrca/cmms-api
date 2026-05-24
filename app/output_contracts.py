"""AI output contract schema management and validation."""

import json
import sqlite3
import time
from typing import Any

from fastapi import HTTPException

from .config import DEFAULT_CMMS_INTAKE_CONTRACT
from .db import db_execute, db_fetchall, db_fetchone


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_default_output_contracts() -> None:
    target_version = "v7"
    row = db_fetchone(
        "SELECT id FROM ai_output_contracts WHERE endpoint = ? AND version = ?",
        ("cmms-intake", target_version),
    )
    if row:
        return
    timestamp = now_text()
    db_execute(
        "UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'",
        (timestamp, "cmms-intake"),
    )
    db_execute(
        """
        INSERT INTO ai_output_contracts
        (endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at)
        VALUES (?, ?, ?, 'active', ?, 1, ?, ?)
        """,
        (
            "cmms-intake",
            target_version,
            "Default CMMS intake output contract with controlled inventory, procurement, and orchestration planning",
            json.dumps(DEFAULT_CMMS_INTAKE_CONTRACT),
            timestamp,
            timestamp,
        ),
    )


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value: Any, expected: Any) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    actual = json_type_name(value)
    if actual == "number" and "integer" in expected_types and isinstance(value, int) and not isinstance(value, bool):
        return True
    return actual in expected_types


def active_contract(endpoint: str) -> sqlite3.Row | None:
    return db_fetchone(
        "SELECT * FROM ai_output_contracts WHERE endpoint = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (endpoint,),
    )


def validate_output_contract(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    contract = active_contract(endpoint)
    if not contract:
        return {
            "valid": True,
            "errors": [],
            "warnings": ["No active output contract configured."],
            "contract_version": None,
            "normalized_payload": payload,
        }
    try:
        schema = json.loads(contract["schema_json"])
    except json.JSONDecodeError:
        return {
            "valid": False,
            "errors": ["Active output contract contains invalid schema JSON."],
            "warnings": [],
            "contract_version": contract["version"],
            "normalized_payload": {},
        }

    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, Any] = {}

    if schema.get("type") == "object" and not isinstance(payload, dict):
        errors.append(f"Payload must be object, got {json_type_name(payload)}.")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "contract_version": contract["version"],
            "normalized_payload": {},
        }

    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    for field in required:
        if field not in payload or payload.get(field) is None:
            errors.append(f"Missing required field: {field}")

    for field, value in payload.items():
        field_schema = properties.get(field)
        if not field_schema:
            message = f"Additional property not allowed: {field}"
            if contract["strict_mode"]:
                errors.append(message)
            else:
                warnings.append(message)
                normalized[field] = value
            continue
        if "type" in field_schema and not type_matches(value, field_schema["type"]):
            errors.append(f"Field {field} must be {field_schema['type']}, got {json_type_name(value)}")
            continue
        normalized[field] = value

    for field in properties:
        if field not in normalized and field in payload:
            normalized[field] = payload[field]

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "contract_version": contract["version"],
        "normalized_payload": normalized if len(errors) == 0 else {},
    }


def skipped_ai_validation() -> dict[str, Any]:
    return {
        "enabled": True,
        "valid": None,
        "status": "not_run",
        "message": "Skipped because output contract validation failed.",
        "errors": [],
        "warnings": [],
        "normalized": {},
    }


def read_output_contract(endpoint: str) -> dict[str, Any]:
    row = active_contract(endpoint)
    if not row:
        raise HTTPException(status_code=404, detail="No active contract found")
    result = dict(row)
    result["schema_json"] = json.loads(result["schema_json"])
    return result


def list_output_contracts() -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_output_contracts ORDER BY endpoint, updated_at DESC")
    result = []
    for row in rows:
        item = dict(row)
        item["schema_json"] = json.loads(item["schema_json"])
        result.append(item)
    return result


def list_output_contracts_for_endpoint(endpoint: str) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_output_contracts WHERE endpoint = ? ORDER BY updated_at DESC", (endpoint,))
    result = []
    for row in rows:
        item = dict(row)
        item["schema_json"] = json.loads(item["schema_json"])
        result.append(item)
    return result


def create_output_contract(payload: Any, user: Any) -> dict[str, Any]:
    timestamp = now_text()
    if payload.status == "active":
        db_execute("UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, payload.endpoint))
    try:
        db_execute(
            """
            INSERT INTO ai_output_contracts
            (endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.endpoint,
                payload.version,
                payload.name,
                payload.status,
                json.dumps(payload.schema_def),
                1 if payload.strict_mode else 0,
                timestamp,
                timestamp,
                user.user_id,
                user.user_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Contract endpoint/version already exists") from exc
    row = db_fetchone("SELECT id FROM ai_output_contracts WHERE endpoint = ? AND version = ?", (payload.endpoint, payload.version))
    return {"status": "ok", "contract_id": row["id"] if row else None}


def patch_output_contract(contract_id: int, payload: Any, user: Any) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_output_contracts WHERE id = ?", (contract_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    timestamp = now_text()
    new_status = payload.status if payload.status is not None else row["status"]
    if new_status == "active" and row["status"] != "active":
        db_execute("UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, row["endpoint"]))
    db_execute(
        """
        UPDATE ai_output_contracts
        SET name = ?, status = ?, schema_json = ?, strict_mode = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            new_status,
            json.dumps(payload.schema_def) if payload.schema_def is not None else row["schema_json"],
            1 if (payload.strict_mode if payload.strict_mode is not None else bool(row["strict_mode"])) else 0,
            timestamp,
            user.user_id,
            contract_id,
        ),
    )
    return {"status": "ok", "contract_id": contract_id}


def activate_output_contract(contract_id: int, user: Any) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_output_contracts WHERE id = ?", (contract_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    timestamp = now_text()
    db_execute("UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, row["endpoint"]))
    db_execute("UPDATE ai_output_contracts SET status = 'active', updated_at = ?, updated_by = ? WHERE id = ?", (timestamp, user.user_id, contract_id))
    return {"status": "ok", "contract_id": contract_id}


def validate_contract_sample(contract_id: int, values: dict[str, Any] | None) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_output_contracts WHERE id = ?", (contract_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    schema = json.loads(row["schema_json"])
    pseudo_endpoint = f"__contract_test_{contract_id}"
    timestamp = now_text()
    db_execute(
        """
        INSERT OR REPLACE INTO ai_output_contracts
        (id, endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (-contract_id, pseudo_endpoint, row["version"], row["name"], json.dumps(schema), row["strict_mode"], timestamp, timestamp),
    )
    result = validate_output_contract(pseudo_endpoint, values or {})
    db_execute("DELETE FROM ai_output_contracts WHERE id = ?", (-contract_id,))
    return result
