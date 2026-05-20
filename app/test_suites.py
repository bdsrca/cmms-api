"""Test suite membership and suite run helpers."""

import json
import secrets
import sqlite3
import time
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from .db import db_execute, db_fetchall, db_fetchone


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, default=str)


def parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return time.mktime(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def suite_row_or_404(suite_id: str) -> Any:
    row = db_fetchone("SELECT * FROM ai_test_suites WHERE suite_id = ?", (suite_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return row


def suite_status_from_summary(summary: dict[str, Any]) -> str:
    if summary["zero_error_required"] and summary["error"] > 0:
        return "error"
    if not summary["meets_pass_rate"]:
        return "failed"
    if summary["failed"] > 0:
        return "failed"
    if summary["warning"] > 0:
        return "warning"
    return "passed"


def suite_summary_from_runs(runs: list[dict[str, Any]], suite: Any) -> dict[str, Any]:
    total = len(runs)
    summary: dict[str, Any] = {
        "total": total,
        "passed": 0,
        "failed": 0,
        "warning": 0,
        "error": 0,
        "pass_rate": 0.0,
        "min_pass_rate": float(suite["min_pass_rate"]),
        "meets_pass_rate": False,
        "zero_error_required": bool(suite["zero_error_required"]),
        "zero_error_met": True,
        "status": "failed",
    }
    for run in runs:
        status = run.get("status") or "error"
        if status in {"passed", "failed", "warning", "error"}:
            summary[status] += 1
        else:
            summary["error"] += 1
    summary["pass_rate"] = round(summary["passed"] / total, 4) if total else 0.0
    summary["meets_pass_rate"] = summary["pass_rate"] >= float(suite["min_pass_rate"])
    summary["zero_error_met"] = summary["error"] == 0
    summary["status"] = suite_status_from_summary(summary)
    return summary


async def run_test_suite_row(
    suite: Any,
    prompt_id: int | None = None,
    environment_override: str | None = None,
    user_id: int | None = None,
    *,
    run_test_case_row: Callable[..., Awaitable[dict[str, Any]]],
    prompt_row_for: Callable[[str, int | None], Any],
    supported_prompt_endpoints: set[str],
    test_case_runner_kwargs: dict[str, Any],
) -> dict[str, Any]:
    suite_run_id = "suite_run_" + secrets.token_hex(8)
    started_at = now_text()
    started = parse_timestamp(started_at) or time.time()
    endpoint = suite["endpoint"]
    environment_code = environment_override.upper() if environment_override else suite["environment_code"]
    prompt_row = prompt_row_for(endpoint, prompt_id) if endpoint in supported_prompt_endpoints else None
    case_rows = db_fetchall(
        """
        SELECT tc.*
        FROM ai_test_suite_cases sc
        JOIN ai_test_cases tc ON tc.id = sc.test_case_id
        WHERE sc.suite_id = ? AND sc.enabled = 1 AND tc.enabled = 1
        ORDER BY sc.sort_order, tc.id
        """,
        (suite["suite_id"],),
    )
    runs = []
    for case in case_rows:
        run = await run_test_case_row(case, prompt_id=prompt_id, environment_override=environment_code, **test_case_runner_kwargs)
        runs.append(run)
        db_execute(
            """
            INSERT INTO ai_test_suite_run_cases
            (suite_run_id, test_case_id, test_case_run_id, status, comparison_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (suite_run_id, case["id"], run.get("id"), run["status"], safe_json(run.get("comparison_json") or {})),
        )
    summary = suite_summary_from_runs(runs, suite)
    finished_at = now_text()
    finished = parse_timestamp(finished_at) or time.time()
    duration_ms = int(max(0, (finished - started) * 1000))
    db_execute(
        """
        INSERT INTO ai_test_suite_runs
        (suite_run_id, suite_id, endpoint, environment_code, prompt_id, prompt_version, status,
         started_at, finished_at, duration_ms, summary_json, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            suite_run_id,
            suite["suite_id"],
            endpoint,
            environment_code,
            prompt_row["id"] if prompt_row else None,
            prompt_row["version"] if prompt_row else None,
            summary["status"],
            started_at,
            finished_at,
            duration_ms,
            safe_json(summary),
            user_id,
        ),
    )
    return {
        "suite_run_id": suite_run_id,
        "suite_id": suite["suite_id"],
        "suite_name": suite["name"],
        "endpoint": endpoint,
        "environment_code": environment_code,
        "prompt_id": prompt_row["id"] if prompt_row else None,
        "prompt_version": prompt_row["version"] if prompt_row else None,
        "status": summary["status"],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "summary": summary,
        "runs": runs,
    }


def list_test_suites(endpoint: str | None = None, environment_code: str | None = None, enabled: bool | None = None, required_for_promotion: bool | None = None) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("endpoint = ?")
        params.append(endpoint)
    if environment_code:
        filters.append("environment_code = ?")
        params.append(environment_code.upper())
    if enabled is not None:
        filters.append("enabled = ?")
        params.append(1 if enabled else 0)
    if required_for_promotion is not None:
        filters.append("required_for_promotion = ?")
        params.append(1 if required_for_promotion else 0)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_suites {where} ORDER BY updated_at DESC, id DESC", tuple(params))
    return [dict(row) for row in rows]


def create_test_suite(payload: Any, user: Any) -> dict[str, Any]:
    timestamp = now_text()
    suite_id = "suite_" + secrets.token_hex(6)
    db_execute(
        """
        INSERT INTO ai_test_suites
        (suite_id, name, endpoint, environment_code, description, enabled, required_for_promotion,
         min_pass_rate, zero_regression_required, zero_error_required, tags, created_at, updated_at, created_by, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            suite_id,
            payload.name,
            payload.endpoint,
            payload.environment_code.upper() if payload.environment_code else None,
            payload.description,
            1 if payload.enabled else 0,
            1 if payload.required_for_promotion else 0,
            payload.min_pass_rate,
            1 if payload.zero_regression_required else 0,
            1 if payload.zero_error_required else 0,
            payload.tags,
            timestamp,
            timestamp,
            user.user_id,
            user.user_id,
        ),
    )
    return {"status": "ok", "suite_id": suite_id}


async def run_test_suite_batch(payload: Any, user: Any, **suite_runner_kwargs: Any) -> dict[str, Any]:
    filters = []
    params: list[Any] = []
    if payload.endpoint:
        filters.append("endpoint = ?")
        params.append(payload.endpoint)
    if payload.environment_code:
        filters.append("environment_code = ?")
        params.append(payload.environment_code.upper())
    if payload.required_only:
        filters.append("required_for_promotion = 1")
    if payload.enabled_only:
        filters.append("enabled = 1")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_suites {where} ORDER BY id", tuple(params))
    runs = [await run_test_suite_row(row, prompt_id=payload.prompt_id, environment_override=payload.environment_code, user_id=user.user_id, **suite_runner_kwargs) for row in rows]
    summary: dict[str, Any] = {"total_suites": len(runs), "passed": 0, "failed": 0, "warning": 0, "error": 0, "runs": runs}
    for run in runs:
        status = run["status"]
        summary[status] = summary.get(status, 0) + 1
    return summary


def list_test_suite_runs(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    where = "WHERE r.status = ?" if status else ""
    params: list[Any] = [status] if status else []
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT r.*, s.name AS suite_name
        FROM ai_test_suite_runs r
        LEFT JOIN ai_test_suites s ON s.suite_id = r.suite_id
        {where}
        ORDER BY r.id DESC LIMIT ?
        """,
        tuple(params),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
        result.append(item)
    return result


def get_test_suite_run(suite_run_id: str) -> dict[str, Any] | None:
    row = db_fetchone(
        """
        SELECT r.*, s.name AS suite_name
        FROM ai_test_suite_runs r
        LEFT JOIN ai_test_suites s ON s.suite_id = r.suite_id
        WHERE r.suite_run_id = ?
        """,
        (suite_run_id,),
    )
    if not row:
        return None
    cases = db_fetchall(
        """
        SELECT rc.*, tc.name AS test_case_name, tcr.run_id AS workflow_run_id
        FROM ai_test_suite_run_cases rc
        LEFT JOIN ai_test_cases tc ON tc.id = rc.test_case_id
        LEFT JOIN ai_test_case_runs tcr ON tcr.id = rc.test_case_run_id
        WHERE rc.suite_run_id = ?
        ORDER BY rc.id
        """,
        (suite_run_id,),
    )
    item = dict(row)
    item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
    item["cases"] = []
    for case in cases:
        case_item = dict(case)
        case_item["comparison_json"] = json.loads(case_item["comparison_json"]) if case_item.get("comparison_json") else None
        item["cases"].append(case_item)
    return item


def get_test_suite(suite_id: str) -> dict[str, Any]:
    row = suite_row_or_404(suite_id)
    cases = db_fetchall(
        """
        SELECT sc.*, tc.name, tc.endpoint, tc.environment_code, tc.input_text, tc.enabled AS test_case_enabled
        FROM ai_test_suite_cases sc
        JOIN ai_test_cases tc ON tc.id = sc.test_case_id
        WHERE sc.suite_id = ?
        ORDER BY sc.sort_order, tc.id
        """,
        (suite_id,),
    )
    item = dict(row)
    item["cases"] = [dict(case) for case in cases]
    return item


def patch_test_suite(suite_id: str, payload: Any, user: Any) -> dict[str, Any]:
    row = suite_row_or_404(suite_id)
    environment_code = payload.environment_code.upper() if payload.environment_code is not None and payload.environment_code else (None if payload.environment_code == "" else row["environment_code"])
    db_execute(
        """
        UPDATE ai_test_suites
        SET name = ?, endpoint = ?, environment_code = ?, description = ?, enabled = ?, required_for_promotion = ?,
            min_pass_rate = ?, zero_regression_required = ?, zero_error_required = ?, tags = ?, updated_at = ?, updated_by = ?
        WHERE suite_id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            payload.endpoint if payload.endpoint is not None else row["endpoint"],
            environment_code,
            payload.description if payload.description is not None else row["description"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            1 if (payload.required_for_promotion if payload.required_for_promotion is not None else bool(row["required_for_promotion"])) else 0,
            payload.min_pass_rate if payload.min_pass_rate is not None else row["min_pass_rate"],
            1 if (payload.zero_regression_required if payload.zero_regression_required is not None else bool(row["zero_regression_required"])) else 0,
            1 if (payload.zero_error_required if payload.zero_error_required is not None else bool(row["zero_error_required"])) else 0,
            payload.tags if payload.tags is not None else row["tags"],
            now_text(),
            user.user_id,
            suite_id,
        ),
    )
    return {"status": "ok", "suite_id": suite_id}


def delete_test_suite(suite_id: str) -> dict[str, Any]:
    suite_row_or_404(suite_id)
    db_execute("DELETE FROM ai_test_suite_cases WHERE suite_id = ?", (suite_id,))
    db_execute("DELETE FROM ai_test_suites WHERE suite_id = ?", (suite_id,))
    return {"status": "ok", "suite_id": suite_id}


def add_test_suite_case(suite_id: str, payload: Any) -> dict[str, Any]:
    suite_row_or_404(suite_id)
    case = db_fetchone("SELECT id FROM ai_test_cases WHERE id = ?", (payload.test_case_id,))
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    try:
        db_execute(
            """
            INSERT INTO ai_test_suite_cases (suite_id, test_case_id, sort_order, enabled)
            VALUES (?, ?, ?, ?)
            """,
            (suite_id, payload.test_case_id, payload.sort_order, 1 if payload.enabled else 0),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Test case is already in this suite") from exc
    return {"status": "ok", "suite_id": suite_id, "test_case_id": payload.test_case_id}


def remove_test_suite_case(suite_id: str, test_case_id: int) -> dict[str, Any]:
    suite_row_or_404(suite_id)
    db_execute("DELETE FROM ai_test_suite_cases WHERE suite_id = ? AND test_case_id = ?", (suite_id, test_case_id))
    return {"status": "ok", "suite_id": suite_id, "test_case_id": test_case_id}


async def run_test_suite(suite_id: str, payload: Any | None = None, user: Any | None = None, **suite_runner_kwargs: Any) -> dict[str, Any]:
    suite = suite_row_or_404(suite_id)
    return await run_test_suite_row(suite, prompt_id=payload.prompt_id if payload else None, environment_override=payload.environment_code if payload else None, user_id=user.user_id if user else None, **suite_runner_kwargs)
