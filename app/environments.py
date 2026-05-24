"""Environment and code-list management helpers."""

import csv
import json
import time
from io import StringIO
from typing import Any

from fastapi import HTTPException

from .config import ALLOWED_REQUEST_TYPES, CODE_CATEGORIES
from .db import DB_LOCK, db_connect, db_execute, db_fetchall, db_fetchone
from .validation_rules import ensure_validation_rules, reset_validation_rules


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_default_environment() -> None:
    exists = db_fetchone("SELECT environment_code FROM environments WHERE environment_code = 'DEFAULT'")
    if exists:
        return
    timestamp = now_text()
    db_execute(
        """
        INSERT INTO environments (environment_code, name, enabled, default_workflow_mode, created_at, updated_at)
        VALUES (?, ?, 1, 'fast', ?, ?)
        """,
        ("DEFAULT", "Default local test", timestamp, timestamp),
    )
    defaults = {
        "buildings": ["ARC", "CAMPUSVIEW", "ZONE-18"],
        "rooms": ["205", "301", "110"],
        "priorities": ["LOW", "NORMAL", "URGENT"],
        "work_order_types": sorted(ALLOWED_REQUEST_TYPES - {"Unknown"}),
        "assign_to": ["Facilities"],
        "issue_to_employee_number": ["0000"],
        "job_type": ["Maintenance"],
    }
    for category, values in defaults.items():
        import_code_values("DEFAULT", category, values, replace=False)
    reset_validation_rules("DEFAULT")


def import_code_values(environment_code: str, category: str, values: list[str], replace: bool) -> int:
    if category not in CODE_CATEGORIES and not category.startswith("custom:"):
        raise HTTPException(status_code=400, detail="Invalid code category")
    cleaned = []
    seen = set()
    for value in values:
        code = str(value).strip()
        if code and code not in seen:
            cleaned.append(code)
            seen.add(code)
    with DB_LOCK:
        with db_connect() as conn:
            if replace:
                conn.execute(
                    "DELETE FROM code_values WHERE environment_code = ? AND category = ?",
                    (environment_code, category),
                )
            for code in cleaned:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO code_values
                    (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, NULL, NULL, 'Manual', 1, ?, ?)
                    """,
                    (environment_code, category, code, code, now_text(), now_text()),
                )
            conn.commit()
    return len(cleaned)


def parse_code_text(text: str) -> list[str]:
    return [row["code"] for row in parse_code_rows(text)]


def parse_code_rows(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []
    values: list[dict[str, str]] = []
    reader = csv.reader(StringIO(text))
    for row in reader:
        if not row:
            continue
        code = row[0].strip() if len(row) > 0 else ""
        if not code:
            continue
        values.append(
            {
                "code": code,
                "label": row[1].strip() if len(row) > 1 and row[1].strip() else code,
                "aliases": row[2].strip() if len(row) > 2 else "",
                "metadata_json": row[3].strip() if len(row) > 3 else "",
            }
        )
    return values


def preview_code_import(environment_code: str, category: str, text: str) -> dict[str, Any]:
    rows = parse_code_rows(text)
    existing_rows = db_fetchall(
        "SELECT code FROM code_values WHERE environment_code = ? AND category = ?",
        (environment_code, category),
    )
    existing = {row["code"] for row in existing_rows}
    seen: set[str] = set()
    valid = []
    duplicates = []
    invalid = []
    for row in rows:
        code = row["code"]
        if not code:
            invalid.append(row)
        elif code in seen:
            duplicates.append(row)
        else:
            valid.append(row)
            seen.add(code)
    updates = [row for row in valid if row["code"] in existing]
    inserts = [row for row in valid if row["code"] not in existing]
    return {
        "environment_code": environment_code,
        "category": category,
        "valid_count": len(valid),
        "duplicate_count": len(duplicates),
        "invalid_count": len(invalid),
        "update_count": len(updates),
        "insert_count": len(inserts),
        "valid": valid,
        "duplicates": duplicates,
        "invalid": invalid,
    }


def import_code_rows(environment_code: str, category: str, rows: list[dict[str, str]], replace: bool) -> int:
    if category not in CODE_CATEGORIES and not category.startswith("custom:"):
        raise HTTPException(status_code=400, detail="Invalid code category")
    timestamp = now_text()
    count = 0
    seen: set[str] = set()
    with DB_LOCK:
        with db_connect() as conn:
            if replace:
                conn.execute(
                    "DELETE FROM code_values WHERE environment_code = ? AND category = ?",
                    (environment_code, category),
                )
            for row in rows:
                code = row["code"].strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                metadata = row.get("metadata_json") or None
                if metadata:
                    try:
                        json.loads(metadata)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON for {code}") from exc
                conn.execute(
                    """
                    INSERT INTO code_values
                    (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'Import', 1, ?, ?)
                    ON CONFLICT(environment_code, category, code)
                    DO UPDATE SET label = excluded.label, aliases = excluded.aliases,
                                  metadata_json = excluded.metadata_json, source = excluded.source,
                                  enabled = 1, updated_at = excluded.updated_at
                    """,
                    (
                        environment_code,
                        category,
                        code,
                        row.get("label") or code,
                        row.get("aliases") or None,
                        metadata,
                        timestamp,
                        timestamp,
                    ),
                )
                count += 1
            conn.commit()
    return count


def get_environment_values(environment_code: str) -> dict[str, list[str]]:
    env = db_fetchone(
        "SELECT environment_code FROM environments WHERE environment_code = ? AND enabled = 1",
        (environment_code,),
    )
    if not env:
        raise HTTPException(status_code=400, detail="Invalid or disabled environment_code")
    rows = db_fetchall(
        """
        SELECT category, code FROM code_values
        WHERE environment_code = ? AND enabled = 1
        ORDER BY category, code
        """,
        (environment_code,),
    )
    values: dict[str, list[str]] = {category: [] for category in CODE_CATEGORIES}
    for row in rows:
        values.setdefault(row["category"], []).append(row["code"])
    return values


def list_environments() -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM environments ORDER BY environment_code")
    return [dict(row) for row in rows]


def normalize_workflow_mode(value: Any) -> str:
    return "full" if str(value or "").strip().lower() == "full" else "fast"


def default_workflow_mode(environment_code: str | None) -> str:
    env_code = str(environment_code or "").strip().upper()
    if not env_code:
        return "fast"
    row = db_fetchone(
        "SELECT default_workflow_mode FROM environments WHERE environment_code = ?",
        (env_code,),
    )
    return normalize_workflow_mode(row["default_workflow_mode"] if row else None)


def create_environment(payload: Any) -> dict[str, Any]:
    timestamp = now_text()
    environment_code = payload.environment_code.upper()
    workflow_mode = normalize_workflow_mode(getattr(payload, "default_workflow_mode", None))
    db_execute(
        """
        INSERT INTO environments (environment_code, name, enabled, default_workflow_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(environment_code) DO UPDATE SET
            name = excluded.name,
            enabled = excluded.enabled,
            default_workflow_mode = excluded.default_workflow_mode,
            updated_at = excluded.updated_at
        """,
        (environment_code, payload.name, 1 if payload.enabled else 0, workflow_mode, timestamp, timestamp),
    )
    ensure_validation_rules(environment_code)
    return {"status": "ok", "environment_code": environment_code}


def patch_environment(environment_code: str, payload: Any) -> dict[str, Any]:
    environment_code = environment_code.upper()
    row = db_fetchone("SELECT * FROM environments WHERE environment_code = ?", (environment_code,))
    if not row:
        raise HTTPException(status_code=404, detail="Environment not found")
    db_execute(
        "UPDATE environments SET name = ?, enabled = ?, default_workflow_mode = ?, updated_at = ? WHERE environment_code = ?",
        (
            payload.name if payload.name is not None else row["name"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            normalize_workflow_mode(payload.default_workflow_mode)
            if getattr(payload, "default_workflow_mode", None) is not None
            else normalize_workflow_mode(row["default_workflow_mode"]),
            now_text(),
            environment_code,
        ),
    )
    return {"status": "ok"}


def list_codes(environment_code: str) -> dict[str, Any]:
    environment_code = environment_code.upper()
    values = get_environment_values(environment_code)
    rows = db_fetchall(
        """
        SELECT code_id, environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at
        FROM code_values
        WHERE environment_code = ?
        ORDER BY category, code
        """,
        (environment_code,),
    )
    return {"environment_code": environment_code, "categories": values, "rows": [dict(row) for row in rows]}


def preview_codes(environment_code: str, payload: Any) -> dict[str, Any]:
    return preview_code_import(environment_code.upper(), payload.category, payload.text or "\n".join(payload.values or []))


def import_codes(environment_code: str, payload: Any) -> dict[str, Any]:
    environment_code = environment_code.upper()
    rows = parse_code_rows(payload.text or "\n".join(payload.values or []))
    count = import_code_rows(environment_code, payload.category, rows, payload.replace)
    return {"status": "ok", "environment_code": environment_code, "category": payload.category, "count": count}


def patch_code_value(environment_code: str, code_id: int, payload: Any) -> dict[str, Any]:
    environment_code = environment_code.upper()
    row = db_fetchone(
        "SELECT * FROM code_values WHERE environment_code = ? AND code_id = ?",
        (environment_code, code_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Code value not found")
    metadata = payload.metadata_json if payload.metadata_json is not None else row["metadata_json"]
    if metadata:
        try:
            json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON") from exc
    db_execute(
        """
        UPDATE code_values
        SET code = ?, label = ?, aliases = ?, metadata_json = ?, enabled = ?, source = 'Manual', updated_at = ?
        WHERE code_id = ? AND environment_code = ?
        """,
        (
            payload.code.strip() if payload.code else row["code"],
            payload.label if payload.label is not None else row["label"],
            payload.aliases if payload.aliases is not None else row["aliases"],
            metadata,
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            now_text(),
            code_id,
            environment_code,
        ),
    )
    return {"status": "ok", "code_id": code_id}
