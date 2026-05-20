"""Environment validation rule engine and AI output business validation."""

import time
from typing import Any

from fastapi import HTTPException

from .config import CODE_CATEGORIES, DEFAULT_VALIDATION_RULES
from .db import DB_LOCK, db_connect, db_execute, db_fetchall, db_fetchone


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reset_validation_rules(environment_code: str) -> None:
    timestamp = now_text()
    with DB_LOCK:
        with db_connect() as conn:
            conn.execute("DELETE FROM environment_validation_rules WHERE environment_code = ?", (environment_code,))
            for field_name, label, required, category, must_match, allow_unknown, severity, sort_order in DEFAULT_VALIDATION_RULES:
                conn.execute(
                    """
                    INSERT INTO environment_validation_rules
                    (environment_code, field_name, label, enabled, required, code_category,
                     must_match_code_list, allow_unknown, severity, sort_order, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        environment_code,
                        field_name,
                        label,
                        1 if required else 0,
                        category,
                        1 if must_match else 0,
                        1 if allow_unknown else 0,
                        severity,
                        sort_order,
                        timestamp,
                    ),
                )
            conn.commit()


def ensure_validation_rules(environment_code: str) -> None:
    count = db_fetchone(
        "SELECT COUNT(*) AS count FROM environment_validation_rules WHERE environment_code = ?",
        (environment_code,),
    )
    if not count or count["count"] == 0:
        reset_validation_rules(environment_code)


def get_validation_rules(environment_code: str) -> list[dict[str, Any]]:
    ensure_validation_rules(environment_code)
    rows = db_fetchall(
        """
        SELECT id, environment_code, field_name, label, enabled, required, code_category,
               must_match_code_list, allow_unknown, severity, sort_order, updated_at
        FROM environment_validation_rules
        WHERE environment_code = ?
        ORDER BY sort_order, field_name
        """,
        (environment_code,),
    )
    return [dict(row) for row in rows]


def patch_validation_rule(environment_code: str, rule_id: int, payload: Any) -> dict[str, Any]:
    environment_code = environment_code.upper()
    row = db_fetchone(
        "SELECT * FROM environment_validation_rules WHERE environment_code = ? AND id = ?",
        (environment_code, rule_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Validation rule not found")
    category = payload.code_category if payload.code_category is not None else row["code_category"]
    if category and category not in CODE_CATEGORIES and not category.startswith("custom:"):
        raise HTTPException(status_code=400, detail="Invalid code category")
    db_execute(
        """
        UPDATE environment_validation_rules
        SET enabled = ?, required = ?, code_category = ?, must_match_code_list = ?,
            allow_unknown = ?, severity = ?, updated_at = ?
        WHERE environment_code = ? AND id = ?
        """,
        (
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            1 if (payload.required if payload.required is not None else bool(row["required"])) else 0,
            category,
            1 if (payload.must_match_code_list if payload.must_match_code_list is not None else bool(row["must_match_code_list"])) else 0,
            1 if (payload.allow_unknown if payload.allow_unknown is not None else bool(row["allow_unknown"])) else 0,
            payload.severity if payload.severity is not None else row["severity"],
            now_text(),
            environment_code,
            rule_id,
        ),
    )
    return {"status": "ok", "rule_id": rule_id}


def reset_environment_validation_rules(environment_code: str) -> dict[str, Any]:
    environment_code = environment_code.upper()
    reset_validation_rules(environment_code)
    return {"status": "ok", "environment_code": environment_code}


def validate_sample(environment_code: str, values: dict[str, Any] | None) -> dict[str, Any]:
    return validate_ai_output(environment_code.upper(), values or {})


def build_code_lookup(environment_code: str, category: str | None) -> dict[str, str]:
    if not category:
        return {}
    rows = db_fetchall(
        """
        SELECT code, label, aliases FROM code_values
        WHERE environment_code = ? AND category = ? AND enabled = 1
        """,
        (environment_code, category),
    )
    lookup: dict[str, str] = {}
    for row in rows:
        code = str(row["code"])
        candidates = [code, row["label"]]
        aliases = row["aliases"] or ""
        candidates.extend(part.strip() for part in aliases.split(",") if part.strip())
        for candidate in candidates:
            if candidate:
                lookup[candidate.strip().casefold()] = code
    return lookup


def validation_issue(field: str, value: Any, message: str) -> dict[str, Any]:
    return {"field": field, "value": value, "message": message}


def validate_ai_output(environment_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    rules = get_validation_rules(environment_code)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized: dict[str, Any] = {}

    for rule in rules:
        if not rule["enabled"]:
            continue
        field = rule["field_name"]
        value = payload.get(field)
        value_text = str(value).strip() if value is not None else ""
        issues = errors if rule["severity"] == "error" else warnings

        if rule["required"] and not value_text:
            issues.append(validation_issue(field, value, f"{rule['label']} is required for environment {environment_code}."))
            continue
        if not value_text:
            continue

        if rule["must_match_code_list"]:
            lookup = build_code_lookup(environment_code, rule["code_category"])
            matched_code = lookup.get(value_text.casefold())
            if matched_code:
                normalized[field] = matched_code
            elif not rule["allow_unknown"]:
                issues.append(
                    validation_issue(
                        field,
                        value,
                        f"{rule['label']} is not in the configured code list for environment {environment_code}.",
                    )
                )
            else:
                normalized[field] = value
        else:
            normalized[field] = value

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "normalized": normalized,
    }
