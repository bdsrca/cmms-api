"""Prompt promotion gate and promotion audit helpers."""

import json
import secrets
import time
from typing import Any

from .db import db_execute, db_fetchall, db_fetchone


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, default=str)


def active_prompt_for_endpoint(endpoint: str) -> Any | None:
    return db_fetchone("SELECT * FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active'", (endpoint,))


def prompt_version_by_id(prompt_id: int) -> Any | None:
    return db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))


def required_suite_readiness(endpoint: str, candidate_prompt_id: int, environment_code: str | None = None) -> dict[str, Any]:
    filters = ["endpoint = ?", "enabled = 1", "required_for_promotion = 1"]
    params: list[Any] = [endpoint]
    if environment_code:
        filters.append("(environment_code IS NULL OR environment_code = ?)")
        params.append(environment_code)
    rows = db_fetchall(f"SELECT * FROM ai_test_suites WHERE {' AND '.join(filters)} ORDER BY name", tuple(params))
    failures = []
    suites = []
    for suite in rows:
        run = db_fetchone(
            """
            SELECT * FROM ai_test_suite_runs
            WHERE suite_id = ? AND prompt_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (suite["suite_id"], candidate_prompt_id),
        )
        run_summary = json.loads(run["summary_json"]) if run and run["summary_json"] else None
        status = run["status"] if run else "missing"
        item = {
            "suite_id": suite["suite_id"],
            "name": suite["name"],
            "environment_code": suite["environment_code"],
            "latest_run_id": run["suite_run_id"] if run else None,
            "status": status,
            "summary": run_summary,
        }
        suites.append(item)
        if not run:
            failures.append({"suite_id": suite["suite_id"], "name": suite["name"], "reason": "No suite run found for candidate prompt."})
        elif run["status"] not in {"passed", "warning"}:
            failures.append({"suite_id": suite["suite_id"], "name": suite["name"], "reason": f"Latest suite run status is {run['status']}."})
    return {
        "required_suites_found": bool(rows),
        "required_suites_passed": not failures,
        "suite_failures": failures,
        "suites": suites,
    }


def check_prompt_promotion_gate(prompt_id: int, comparison_id: str | None = None) -> dict[str, Any]:
    candidate = prompt_version_by_id(prompt_id)
    reasons: list[str] = []
    summary: dict[str, Any] = {}
    suite_readiness = {"required_suites_found": False, "required_suites_passed": True, "suite_failures": [], "suites": []}

    if not candidate:
        return {"allowed": False, "gate_status": "blocked", "reasons": ["Candidate prompt was not found."], "summary": summary, "comparison_id": comparison_id}
    if candidate["status"] == "archived":
        reasons.append("Archived prompts cannot be activated.")
    if candidate["status"] not in {"draft", "active"}:
        reasons.append("Candidate prompt is not eligible for activation.")

    active = active_prompt_for_endpoint(candidate["endpoint"])
    if not active:
        reasons.append(f"No current active prompt exists for endpoint {candidate['endpoint']}.")

    if not comparison_id:
        reasons.append("A completed prompt comparison is required for promotion.")
    else:
        comparison_row = db_fetchone("SELECT * FROM ai_prompt_comparisons WHERE comparison_id = ?", (comparison_id,))
        if not comparison_row:
            reasons.append("Prompt comparison was not found.")
        else:
            try:
                summary = json.loads(comparison_row["summary_json"]) if comparison_row["summary_json"] else {}
            except json.JSONDecodeError:
                summary = {}
                reasons.append("Prompt comparison summary JSON is invalid.")
            if comparison_row["endpoint"] != candidate["endpoint"]:
                reasons.append("Prompt comparison endpoint does not match the candidate prompt endpoint.")
            if active and comparison_row["baseline_prompt_id"] != active["id"]:
                reasons.append("Prompt comparison baseline is not the current active prompt.")
            if comparison_row["candidate_prompt_id"] != candidate["id"]:
                reasons.append("Prompt comparison candidate does not match this prompt.")
            if comparison_row["status"] != "completed":
                reasons.append("Prompt comparison is not completed.")
            if int(summary.get("regressed") or 0) != 0:
                reasons.append("Prompt comparison has regressions.")
            if int(summary.get("error") or 0) != 0:
                reasons.append("Prompt comparison has errors.")
            if int(summary.get("candidate_passed") or 0) < int(summary.get("baseline_passed") or 0):
                reasons.append("Candidate passed fewer test cases than the current active baseline.")
            suite_readiness = required_suite_readiness(candidate["endpoint"], candidate["id"], comparison_row["environment_code"])
            if suite_readiness["required_suites_found"] and not suite_readiness["required_suites_passed"]:
                reasons.append("One or more required test suites have not passed for the candidate prompt.")

    allowed = not reasons
    return {
        "allowed": allowed,
        "gate_status": "passed" if allowed else "blocked",
        "reasons": reasons,
        "summary": summary,
        "comparison_id": comparison_id,
        "suite_readiness": suite_readiness,
    }


def record_prompt_promotion(
    endpoint: str,
    previous_prompt_id: int | None,
    promoted_prompt_id: int,
    comparison_id: str | None,
    gate_status: str,
    override_used: bool,
    override_reason: str | None,
    promoted_by: int | None,
    summary: dict[str, Any] | None,
) -> str:
    promotion_id = "promo_" + secrets.token_hex(8)
    db_execute(
        """
        INSERT INTO ai_prompt_promotions
        (promotion_id, endpoint, previous_prompt_id, promoted_prompt_id, comparison_id, gate_status,
         override_used, override_reason, promoted_by, promoted_at, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            promotion_id,
            endpoint,
            previous_prompt_id,
            promoted_prompt_id,
            comparison_id,
            gate_status,
            1 if override_used else 0,
            override_reason,
            promoted_by,
            now_text(),
            safe_json(summary or {}),
        ),
    )
    return promotion_id


def list_prompt_promotions(endpoint: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("p.endpoint = ?")
        params.append(endpoint)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT p.*, prev.version AS previous_version, promoted.version AS promoted_version, u.username AS promoted_by_username
        FROM ai_prompt_promotions p
        LEFT JOIN ai_prompt_versions prev ON prev.id = p.previous_prompt_id
        LEFT JOIN ai_prompt_versions promoted ON promoted.id = p.promoted_prompt_id
        LEFT JOIN users u ON u.user_id = p.promoted_by
        {where}
        ORDER BY p.id DESC LIMIT ?
        """,
        tuple(params),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
        result.append(item)
    return result


def get_prompt_promotion(promotion_id: str) -> dict[str, Any] | None:
    row = db_fetchone(
        """
        SELECT p.*, prev.version AS previous_version, promoted.version AS promoted_version, u.username AS promoted_by_username
        FROM ai_prompt_promotions p
        LEFT JOIN ai_prompt_versions prev ON prev.id = p.previous_prompt_id
        LEFT JOIN ai_prompt_versions promoted ON promoted.id = p.promoted_prompt_id
        LEFT JOIN users u ON u.user_id = p.promoted_by
        WHERE p.promotion_id = ?
        """,
        (promotion_id,),
    )
    if not row:
        return None
    item = dict(row)
    item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
    return item
