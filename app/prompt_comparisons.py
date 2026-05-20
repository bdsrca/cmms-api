"""Prompt A/B comparison helpers."""

import json
import secrets
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


def extract_result_value(response: dict[str, Any], field: str) -> Any:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    fields = response.get("fields") if isinstance(response.get("fields"), dict) else {}
    if field in result:
        return result.get(field)
    if field == "work_order_type":
        return result.get("work_order_type") or response.get("request_type")
    return fields.get(field)


def status_is_passing(status: str | None) -> bool:
    return status in {"passed", "warning"}


def classify_prompt_comparison_result(baseline_status: str, candidate_status: str) -> str:
    if baseline_status == "error" or candidate_status == "error":
        return "error"
    baseline_passed = status_is_passing(baseline_status)
    candidate_passed = status_is_passing(candidate_status)
    if not baseline_passed and candidate_passed:
        return "improved"
    if baseline_passed and not candidate_passed:
        return "regressed"
    if baseline_passed and candidate_passed:
        return "unchanged_pass"
    return "unchanged_fail"


def prompt_comparison_field_differences(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    fields = ["summary", "building", "room", "priority", "work_order_type", "assign_to", "issue_to", "job_type"]
    differences = []
    for field in fields:
        baseline_value = extract_result_value(baseline, field)
        candidate_value = extract_result_value(candidate, field)
        if baseline_value != candidate_value:
            differences.append({"field": field, "baseline": baseline_value, "candidate": candidate_value})
    baseline_contract = baseline.get("contract", {}).get("valid") if isinstance(baseline.get("contract"), dict) else None
    candidate_contract = candidate.get("contract", {}).get("valid") if isinstance(candidate.get("contract"), dict) else None
    if baseline_contract != candidate_contract:
        differences.append({"field": "contract_valid", "baseline": baseline_contract, "candidate": candidate_contract})
    baseline_env = baseline.get("ai_validation", {}).get("valid") if isinstance(baseline.get("ai_validation"), dict) else None
    candidate_env = candidate.get("ai_validation", {}).get("valid") if isinstance(candidate.get("ai_validation"), dict) else None
    if baseline_env != candidate_env:
        differences.append({"field": "environment_valid", "baseline": baseline_env, "candidate": candidate_env})
    return differences


def prompt_comparison_case_json(test_case: Any, baseline: dict[str, Any], candidate: dict[str, Any], result: str) -> dict[str, Any]:
    return {
        "test_case_id": test_case["id"],
        "test_case_name": test_case["name"],
        "baseline": {
            "prompt_id": baseline.get("prompt_id"),
            "prompt_version": baseline.get("prompt_version"),
            "status": baseline.get("status"),
            "run_id": baseline.get("run_id"),
            "duration_ms": baseline.get("duration_ms"),
        },
        "candidate": {
            "prompt_id": candidate.get("prompt_id"),
            "prompt_version": candidate.get("prompt_version"),
            "status": candidate.get("status"),
            "run_id": candidate.get("run_id"),
            "duration_ms": candidate.get("duration_ms"),
        },
        "result": result,
        "field_differences": prompt_comparison_field_differences(baseline.get("actual_json") or {}, candidate.get("actual_json") or {}),
    }


def prompt_comparison_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total": len(cases),
        "baseline_passed": 0,
        "candidate_passed": 0,
        "improved": 0,
        "regressed": 0,
        "unchanged_pass": 0,
        "unchanged_fail": 0,
        "error": 0,
        "baseline_avg_duration_ms": 0,
        "candidate_avg_duration_ms": 0,
    }
    baseline_durations = []
    candidate_durations = []
    for case in cases:
        baseline = case.get("baseline", {})
        candidate = case.get("candidate", {})
        if status_is_passing(baseline.get("status")):
            summary["baseline_passed"] += 1
        if status_is_passing(candidate.get("status")):
            summary["candidate_passed"] += 1
        result = case.get("result")
        if result in {"improved", "regressed", "unchanged_pass", "unchanged_fail", "error"}:
            summary[result] += 1
        if isinstance(baseline.get("duration_ms"), int):
            baseline_durations.append(baseline["duration_ms"])
        if isinstance(candidate.get("duration_ms"), int):
            candidate_durations.append(candidate["duration_ms"])
    if baseline_durations:
        summary["baseline_avg_duration_ms"] = round(sum(baseline_durations) / len(baseline_durations), 1)
    if candidate_durations:
        summary["candidate_avg_duration_ms"] = round(sum(candidate_durations) / len(candidate_durations), 1)
    return summary


async def run_prompt_comparison(
    payload: Any,
    user: Any,
    *,
    prompt_version_by_id: Callable[[int], Any],
    run_test_case_row: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    baseline_prompt = prompt_version_by_id(payload.baseline_prompt_id)
    candidate_prompt = prompt_version_by_id(payload.candidate_prompt_id)
    if not baseline_prompt or not candidate_prompt:
        raise HTTPException(status_code=404, detail="Baseline or candidate prompt was not found")
    if baseline_prompt["endpoint"] != payload.endpoint or candidate_prompt["endpoint"] != payload.endpoint:
        raise HTTPException(status_code=400, detail="Both prompt versions must match the requested endpoint")
    comparison_id = "cmp_" + secrets.token_hex(8)
    started_at = now_text()
    started = parse_timestamp(started_at) or time.time()
    environment_code = payload.environment_code.upper() if payload.environment_code else None
    db_execute(
        """
        INSERT INTO ai_prompt_comparisons
        (comparison_id, endpoint, environment_code, baseline_prompt_id, candidate_prompt_id, status, started_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (comparison_id, payload.endpoint, environment_code, payload.baseline_prompt_id, payload.candidate_prompt_id, "running", started_at, user.user_id),
    )
    filters = ["endpoint = ?"]
    params: list[Any] = [payload.endpoint]
    if environment_code:
        filters.append("environment_code = ?")
        params.append(environment_code)
    if payload.enabled_only:
        filters.append("enabled = 1")
    rows = db_fetchall(f"SELECT * FROM ai_test_cases WHERE {' AND '.join(filters)} ORDER BY id", tuple(params))
    case_jsons = []
    for row in rows:
        baseline_run = await run_test_case_row(row, prompt_id=payload.baseline_prompt_id, environment_override=environment_code)
        candidate_run = await run_test_case_row(row, prompt_id=payload.candidate_prompt_id, environment_override=environment_code)
        result = classify_prompt_comparison_result(baseline_run["status"], candidate_run["status"])
        case_json = prompt_comparison_case_json(row, baseline_run, candidate_run, result)
        case_jsons.append(case_json)
        db_execute(
            """
            INSERT INTO ai_prompt_comparison_cases
            (comparison_id, test_case_id, baseline_run_id, candidate_run_id, baseline_status, candidate_status, result, comparison_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comparison_id,
                row["id"],
                baseline_run.get("run_id"),
                candidate_run.get("run_id"),
                baseline_run["status"],
                candidate_run["status"],
                result,
                safe_json(case_json),
            ),
        )
    summary = prompt_comparison_summary(case_jsons)
    finished_at = now_text()
    finished = parse_timestamp(finished_at) or time.time()
    duration_ms = int(max(0, (finished - started) * 1000))
    status = "completed"
    db_execute(
        """
        UPDATE ai_prompt_comparisons
        SET status = ?, finished_at = ?, duration_ms = ?, summary_json = ?
        WHERE comparison_id = ?
        """,
        (status, finished_at, duration_ms, safe_json(summary), comparison_id),
    )
    return {
        "comparison_id": comparison_id,
        "endpoint": payload.endpoint,
        "environment_code": environment_code,
        "baseline_prompt_id": payload.baseline_prompt_id,
        "candidate_prompt_id": payload.candidate_prompt_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "summary": summary,
        "cases": case_jsons,
    }


def list_prompt_comparisons(endpoint: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("c.endpoint = ?")
        params.append(endpoint)
    if status:
        filters.append("c.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT c.*, bp.version AS baseline_version, cp.version AS candidate_version
        FROM ai_prompt_comparisons c
        LEFT JOIN ai_prompt_versions bp ON bp.id = c.baseline_prompt_id
        LEFT JOIN ai_prompt_versions cp ON cp.id = c.candidate_prompt_id
        {where}
        ORDER BY c.id DESC LIMIT ?
        """,
        tuple(params),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
        result.append(item)
    return result


def get_prompt_comparison(comparison_id: str) -> dict[str, Any] | None:
    row = db_fetchone(
        """
        SELECT c.*, bp.version AS baseline_version, cp.version AS candidate_version
        FROM ai_prompt_comparisons c
        LEFT JOIN ai_prompt_versions bp ON bp.id = c.baseline_prompt_id
        LEFT JOIN ai_prompt_versions cp ON cp.id = c.candidate_prompt_id
        WHERE c.comparison_id = ?
        """,
        (comparison_id,),
    )
    if not row:
        return None
    cases = db_fetchall(
        """
        SELECT pc.*, tc.name AS test_case_name
        FROM ai_prompt_comparison_cases pc
        LEFT JOIN ai_test_cases tc ON tc.id = pc.test_case_id
        WHERE pc.comparison_id = ?
        ORDER BY pc.id
        """,
        (comparison_id,),
    )
    item = dict(row)
    item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
    item["cases"] = []
    for case in cases:
        case_item = dict(case)
        case_item["comparison_json"] = json.loads(case_item["comparison_json"]) if case_item.get("comparison_json") else None
        item["cases"].append(case_item)
    return item
