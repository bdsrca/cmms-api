"""Saved test case, replay, and regression comparison helpers."""

import json
import time
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from .db import DB_LOCK, db_connect, db_execute, db_fetchall, db_fetchone


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


def extract_result_value(response: dict[str, Any], field: str) -> Any:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    fields = response.get("fields") if isinstance(response.get("fields"), dict) else {}
    if field in result:
        return result.get(field)
    if field == "work_order_type":
        return result.get("work_order_type") or response.get("request_type")
    return fields.get(field)


def issue_fields(items: Any) -> set[str]:
    fields: set[str] = set()
    if not isinstance(items, list):
        return fields
    for item in items:
        if isinstance(item, dict):
            value = item.get("field") or item.get("message") or ""
        else:
            value = str(item)
        fields.add(str(value).lower())
    return fields


def compare_test_case_result(expected_json: dict[str, Any] | None, actual_response: dict[str, Any]) -> dict[str, Any]:
    expected = expected_json or {}
    field_results = []
    passed = True
    for field in ["building", "room", "priority", "work_order_type", "assign_to", "issue_to", "job_type"]:
        if field not in expected:
            continue
        actual = extract_result_value(actual_response, field)
        ok = actual == expected.get(field)
        passed = passed and ok
        field_results.append({"field": field, "expected": expected.get(field), "actual": actual, "passed": ok})

    summary_results = []
    summary = str(extract_result_value(actual_response, "summary") or actual_response.get("summary") or "").lower()
    for needle in expected.get("summary_contains") or []:
        ok = str(needle).lower() in summary
        passed = passed and ok
        summary_results.append({"contains": needle, "passed": ok})

    contract_result = {}
    if "contract_valid" in expected:
        actual = actual_response.get("contract", {}).get("valid") if isinstance(actual_response.get("contract"), dict) else None
        ok = actual == expected["contract_valid"]
        passed = passed and ok
        contract_result = {"expected": expected["contract_valid"], "actual": actual, "passed": ok}

    environment_result = {}
    ai_validation = actual_response.get("ai_validation") if isinstance(actual_response.get("ai_validation"), dict) else {}
    if "environment_valid" in expected:
        actual = ai_validation.get("valid")
        ok = actual == expected["environment_valid"]
        passed = passed and ok
        environment_result["valid"] = {"expected": expected["environment_valid"], "actual": actual, "passed": ok}

    expected_errors = {str(value).lower() for value in expected.get("expected_errors") or []}
    expected_warnings = {str(value).lower() for value in expected.get("expected_warnings") or []}
    actual_error_fields = issue_fields(ai_validation.get("errors"))
    actual_warning_fields = issue_fields(ai_validation.get("warnings"))
    if expected_errors:
        ok = all(any(expected_field in actual_field for actual_field in actual_error_fields) for expected_field in expected_errors)
        passed = passed and ok
        environment_result["expected_errors"] = {"expected": sorted(expected_errors), "actual": sorted(actual_error_fields), "passed": ok}
    if expected_warnings:
        ok = all(any(expected_field in actual_field for actual_field in actual_warning_fields) for expected_field in expected_warnings)
        passed = passed and ok
        environment_result["expected_warnings"] = {"expected": sorted(expected_warnings), "actual": sorted(actual_warning_fields), "passed": ok}

    return {
        "passed": passed,
        "field_results": field_results,
        "summary_results": summary_results,
        "contract_result": contract_result,
        "environment_result": environment_result,
        "summary": "All assertions passed." if passed else "One or more assertions failed.",
    }


def test_case_run_status(comparison: dict[str, Any]) -> str:
    if comparison.get("passed"):
        return "passed"
    return "failed"


def list_test_cases(endpoint: str | None = None, environment_code: str | None = None, enabled: bool | None = None) -> list[dict[str, Any]]:
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
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_cases {where} ORDER BY updated_at DESC, id DESC", tuple(params))
    result = []
    for row in rows:
        item = dict(row)
        item["expected_json"] = json.loads(item["expected_json"]) if item.get("expected_json") else None
        result.append(item)
    return result


def create_test_case(payload: Any, user: Any) -> dict[str, Any]:
    timestamp = now_text()
    with DB_LOCK:
        with db_connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_test_cases
                (name, endpoint, environment_code, input_text, source, expected_json, enabled, tags, notes, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.endpoint,
                    payload.environment_code.upper() if payload.environment_code else None,
                    payload.input_text,
                    payload.source or "manual",
                    safe_json(payload.expected_json),
                    1 if payload.enabled else 0,
                    payload.tags,
                    payload.notes,
                    timestamp,
                    timestamp,
                    user.user_id,
                    user.user_id,
                ),
            )
            conn.commit()
            return {"status": "ok", "test_case_id": int(cursor.lastrowid)}


def get_test_case_row(test_case_id: int) -> Any | None:
    return db_fetchone("SELECT * FROM ai_test_cases WHERE id = ?", (test_case_id,))


def get_test_case(test_case_id: int) -> dict[str, Any] | None:
    row = get_test_case_row(test_case_id)
    if not row:
        return None
    item = dict(row)
    item["expected_json"] = json.loads(item["expected_json"]) if item.get("expected_json") else None
    return item


def patch_test_case(test_case_id: int, payload: Any, user: Any) -> dict[str, Any]:
    row = get_test_case_row(test_case_id)
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")
    endpoint = payload.endpoint if payload.endpoint is not None else row["endpoint"]
    environment_code = payload.environment_code.upper() if payload.environment_code is not None and payload.environment_code else (None if payload.environment_code == "" else row["environment_code"])
    db_execute(
        """
        UPDATE ai_test_cases
        SET name = ?, endpoint = ?, environment_code = ?, input_text = ?, source = ?, expected_json = ?,
            enabled = ?, tags = ?, notes = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            endpoint,
            environment_code,
            payload.input_text if payload.input_text is not None else row["input_text"],
            payload.source if payload.source is not None else row["source"],
            safe_json(payload.expected_json) if payload.expected_json is not None else row["expected_json"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            payload.tags if payload.tags is not None else row["tags"],
            payload.notes if payload.notes is not None else row["notes"],
            now_text(),
            user.user_id,
            test_case_id,
        ),
    )
    return {"status": "ok", "test_case_id": test_case_id}


def delete_test_case(test_case_id: int) -> dict[str, Any]:
    db_execute("DELETE FROM ai_test_cases WHERE id = ?", (test_case_id,))
    return {"status": "ok", "test_case_id": test_case_id}


async def run_test_case_row(
    row: Any,
    prompt_id: int | None = None,
    environment_override: str | None = None,
    *,
    endpoint_runner: Callable[..., Awaitable[dict[str, Any]]],
    prompt_row_for: Callable[[str, int | None], Any],
    supported_prompt_endpoints: set[str],
) -> dict[str, Any]:
    started_at = now_text()
    started = parse_timestamp(started_at) or time.time()
    endpoint = row["endpoint"]
    environment_code = environment_override.upper() if environment_override else row["environment_code"]
    prompt_row = prompt_row_for(endpoint, prompt_id) if endpoint in supported_prompt_endpoints else None
    try:
        actual = await endpoint_runner(endpoint, row["input_text"], environment_code, source="test_case", prompt_id=prompt_id)
        comparison = compare_test_case_result(json.loads(row["expected_json"]) if row["expected_json"] else None, actual)
        status = test_case_run_status(comparison)
        if status == "passed" and isinstance(actual.get("ai_validation"), dict) and actual["ai_validation"].get("warnings"):
            status = "warning"
        error_message = None
    except Exception as exc:
        actual = {}
        comparison = {"passed": False, "summary": str(exc), "field_results": [], "contract_result": {}, "environment_result": {}}
        status = "error"
        error_message = str(exc)
    finished_at = now_text()
    finished = parse_timestamp(finished_at) or time.time()
    duration_ms = int(max(0, (finished - started) * 1000))
    run_id = actual.get("run_id") if isinstance(actual, dict) else None
    with DB_LOCK:
        with db_connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_test_case_runs
                (test_case_id, run_id, endpoint, environment_code, prompt_id, prompt_version, status, started_at, finished_at, duration_ms, actual_json, comparison_json, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    run_id,
                    endpoint,
                    environment_code,
                    prompt_row["id"] if prompt_row else None,
                    prompt_row["version"] if prompt_row else None,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    safe_json(actual),
                    safe_json(comparison),
                    error_message,
                ),
            )
            conn.commit()
            run_record_id = int(cursor.lastrowid)
    return {"id": run_record_id, "test_case_id": row["id"], "run_id": run_id, "endpoint": endpoint, "environment_code": environment_code, "prompt_id": prompt_row["id"] if prompt_row else None, "prompt_version": prompt_row["version"] if prompt_row else None, "status": status, "duration_ms": duration_ms, "actual_json": actual, "comparison_json": comparison, "error_message": error_message}


async def run_test_case(
    test_case_id: int,
    payload: Any | None = None,
    **runner_kwargs: Any,
) -> dict[str, Any]:
    row = get_test_case_row(test_case_id)
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")
    return await run_test_case_row(row, prompt_id=payload.prompt_id if payload else None, environment_override=payload.environment_code if payload else None, **runner_kwargs)


async def run_test_case_batch(payload: Any, **runner_kwargs: Any) -> dict[str, Any]:
    filters = []
    params: list[Any] = []
    if payload.endpoint:
        filters.append("endpoint = ?")
        params.append(payload.endpoint)
    if payload.environment_code:
        filters.append("environment_code = ?")
        params.append(payload.environment_code.upper())
    if payload.enabled_only:
        filters.append("enabled = 1")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_cases {where} ORDER BY id", tuple(params))
    runs = [await run_test_case_row(row, prompt_id=payload.prompt_id, **runner_kwargs) for row in rows]
    summary = {"total": len(runs), "passed": 0, "failed": 0, "warning": 0, "error": 0, "runs": runs}
    for run in runs:
        summary[run["status"]] = summary.get(run["status"], 0) + 1
    return summary


def list_test_case_runs(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    where = "WHERE r.status = ?" if status else ""
    params: list[Any] = [status] if status else []
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT r.*, c.name AS test_case_name
        FROM ai_test_case_runs r
        LEFT JOIN ai_test_cases c ON c.id = r.test_case_id
        {where}
        ORDER BY r.id DESC LIMIT ?
        """,
        tuple(params),
    )
    return [dict(row) for row in rows]


def get_test_case_run(run_id: str) -> dict[str, Any] | None:
    row = db_fetchone("SELECT * FROM ai_test_case_runs WHERE run_id = ? OR id = ?", (run_id, run_id if str(run_id).isdigit() else -1))
    if not row:
        return None
    item = dict(row)
    item["actual_json"] = json.loads(item["actual_json"]) if item.get("actual_json") else None
    item["comparison_json"] = json.loads(item["comparison_json"]) if item.get("comparison_json") else None
    return item


async def create_test_case_from_workflow_run(run_id: str, payload: Any, user: Any) -> dict[str, Any]:
    row = db_fetchone(
        """
        SELECT c.*, r.actual_json
        FROM ai_test_case_runs r
        JOIN ai_test_cases c ON c.id = r.test_case_id
        WHERE r.run_id = ?
        ORDER BY r.id DESC LIMIT 1
        """,
        (run_id,),
    )
    if not row:
        raise HTTPException(status_code=400, detail="This workflow run cannot create a test case because the original input text was not stored.")
    expected_json = payload.expected_json
    if expected_json is None and row["actual_json"]:
        try:
            actual = json.loads(row["actual_json"])
            expected_json = {
                "building": extract_result_value(actual, "building"),
                "room": extract_result_value(actual, "room"),
                "priority": extract_result_value(actual, "priority"),
                "work_order_type": extract_result_value(actual, "work_order_type"),
                "contract_valid": actual.get("contract", {}).get("valid") if isinstance(actual.get("contract"), dict) else None,
                "environment_valid": actual.get("ai_validation", {}).get("valid") if isinstance(actual.get("ai_validation"), dict) else None,
            }
        except json.JSONDecodeError:
            expected_json = None

    class RequestPayload:
        pass

    request_payload = RequestPayload()
    request_payload.name = payload.name
    request_payload.endpoint = row["endpoint"]
    request_payload.environment_code = row["environment_code"]
    request_payload.input_text = row["input_text"]
    request_payload.source = "workflow_run"
    request_payload.expected_json = expected_json
    request_payload.enabled = True
    request_payload.tags = payload.tags
    request_payload.notes = payload.notes
    return create_test_case(request_payload, user)


async def replay_workflow_run(run_id: str, payload: Any | None = None, **runner_kwargs: Any) -> dict[str, Any]:
    row = db_fetchone(
        """
        SELECT c.*
        FROM ai_test_case_runs r
        JOIN ai_test_cases c ON c.id = r.test_case_id
        WHERE r.run_id = ?
        ORDER BY r.id DESC LIMIT 1
        """,
        (run_id,),
    )
    if not row:
        raise HTTPException(status_code=400, detail="This workflow run cannot be replayed because the original input text was not stored.")
    return await run_test_case_row(row, prompt_id=payload.prompt_id if payload else None, environment_override=payload.environment_code if payload else None, **runner_kwargs)
