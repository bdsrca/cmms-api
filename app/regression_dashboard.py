"""Read-only regression dashboard aggregation helpers."""

import json
from typing import Any

from .db import db_fetchall, db_fetchone


def json_or_empty(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def regression_required_suite_readiness() -> dict[str, Any]:
    rows = db_fetchall(
        """
        SELECT * FROM ai_test_suites
        WHERE enabled = 1 AND required_for_promotion = 1
        ORDER BY endpoint, environment_code, name
        """
    )
    items = []
    counts = {"total": len(rows), "passed": 0, "failed": 0, "not_run": 0}
    for suite in rows:
        run = db_fetchone(
            """
            SELECT * FROM ai_test_suite_runs
            WHERE suite_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (suite["suite_id"],),
        )
        if not run:
            status = "not_run"
            summary = {}
            counts["not_run"] += 1
        else:
            summary = json_or_empty(run["summary_json"])
            status = "passed" if run["status"] == "passed" else ("warning" if run["status"] == "warning" else "failed")
            if status == "passed":
                counts["passed"] += 1
            else:
                counts["failed"] += 1
        items.append(
            {
                "suite_id": suite["suite_id"],
                "name": suite["name"],
                "endpoint": suite["endpoint"],
                "environment_code": suite["environment_code"],
                "latest_suite_run_id": run["suite_run_id"] if run else None,
                "latest_prompt_version": run["prompt_version"] if run else None,
                "last_run_at": run["started_at"] if run else None,
                "pass_rate": summary.get("pass_rate"),
                "status": status,
            }
        )
    counts["items"] = items
    return counts


def regression_latest_suite_runs(limit: int = 10) -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT r.*, s.name AS suite_name
        FROM ai_test_suite_runs r
        LEFT JOIN ai_test_suites s ON s.suite_id = r.suite_id
        ORDER BY r.id DESC LIMIT ?
        """,
        (limit,),
    )
    result = []
    for row in rows:
        summary = json_or_empty(row["summary_json"])
        result.append(
            {
                "suite_run_id": row["suite_run_id"],
                "suite_name": row["suite_name"],
                "endpoint": row["endpoint"],
                "environment_code": row["environment_code"],
                "prompt_version": row["prompt_version"],
                "status": row["status"],
                "pass_rate": summary.get("pass_rate"),
                "total": summary.get("total", 0),
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "warning": summary.get("warning", 0),
                "error": summary.get("error", 0),
                "started_at": row["started_at"],
                "duration_ms": row["duration_ms"],
            }
        )
    return result


def regression_recent_prompt_comparisons(limit: int = 10) -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT c.*, bp.version AS baseline_version, cp.version AS candidate_version
        FROM ai_prompt_comparisons c
        LEFT JOIN ai_prompt_versions bp ON bp.id = c.baseline_prompt_id
        LEFT JOIN ai_prompt_versions cp ON cp.id = c.candidate_prompt_id
        ORDER BY c.id DESC LIMIT ?
        """,
        (limit,),
    )
    result = []
    for row in rows:
        summary = json_or_empty(row["summary_json"])
        result.append(
            {
                "comparison_id": row["comparison_id"],
                "endpoint": row["endpoint"],
                "environment_code": row["environment_code"],
                "baseline_prompt": row["baseline_version"] or row["baseline_prompt_id"],
                "candidate_prompt": row["candidate_version"] or row["candidate_prompt_id"],
                "total": summary.get("total", 0),
                "improved": summary.get("improved", 0),
                "regressed": summary.get("regressed", 0),
                "error": summary.get("error", 0),
                "status": row["status"],
                "started_at": row["started_at"],
            }
        )
    return result


def regression_recent_promotions(limit: int = 10) -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT p.*, prev.version AS previous_version, promoted.version AS promoted_version
        FROM ai_prompt_promotions p
        LEFT JOIN ai_prompt_versions prev ON prev.id = p.previous_prompt_id
        LEFT JOIN ai_prompt_versions promoted ON promoted.id = p.promoted_prompt_id
        ORDER BY p.id DESC LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "promotion_id": row["promotion_id"],
            "endpoint": row["endpoint"],
            "previous_prompt": row["previous_version"] or row["previous_prompt_id"],
            "promoted_prompt": row["promoted_version"] or row["promoted_prompt_id"],
            "comparison_id": row["comparison_id"],
            "gate_status": row["gate_status"],
            "override_used": bool(row["override_used"]),
            "promoted_at": row["promoted_at"],
        }
        for row in rows
    ]


def regression_workflow_summary(limit: int = 100) -> dict[str, Any]:
    rows = db_fetchall("SELECT status, duration_ms FROM workflow_runs ORDER BY id DESC LIMIT ?", (limit,))
    summary = {"total": len(rows), "completed": 0, "completed_with_warnings": 0, "failed": 0, "avg_duration_ms": 0}
    durations = []
    for row in rows:
        status = row["status"]
        if status in summary:
            summary[status] += 1
        if row["duration_ms"] is not None:
            durations.append(row["duration_ms"])
    if durations:
        summary["avg_duration_ms"] = round(sum(durations) / len(durations), 1)
    return summary


def regression_top_failing_fields(limit: int = 100) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}

    def add(field: Any) -> None:
        if field is None:
            return
        name = str(field).strip().lower()
        if not name:
            return
        counts[name] = counts.get(name, 0) + 1

    rows = db_fetchall("SELECT actual_json, comparison_json FROM ai_test_case_runs ORDER BY id DESC LIMIT ?", (limit,))
    for row in rows:
        comparison = json_or_empty(row["comparison_json"])
        for result in comparison.get("field_results") or []:
            if isinstance(result, dict) and result.get("passed") is False:
                add(result.get("field"))
        env_result = comparison.get("environment_result") or {}
        for key, value in env_result.items():
            if isinstance(value, dict) and value.get("passed") is False:
                add(key.replace("expected_", ""))
        actual = json_or_empty(row["actual_json"])
        validation = actual.get("ai_validation") if isinstance(actual.get("ai_validation"), dict) else {}
        for issue in (validation.get("errors") or []) + (validation.get("warnings") or []):
            if isinstance(issue, dict):
                add(issue.get("field"))
    return [{"field": field, "count": count} for field, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]]


def regression_recent_validation_failures(limit: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    workflow_rows = db_fetchall("SELECT * FROM workflow_runs WHERE status = 'failed' ORDER BY id DESC LIMIT 10")
    for row in workflow_rows:
        items.append({"timestamp": row["started_at"], "source_type": "workflow", "endpoint": row["endpoint"], "environment_code": row["environment_code"], "field": None, "message": row["error_message"] or "Workflow failed.", "link_id": row["run_id"]})

    test_rows = db_fetchall(
        """
        SELECT r.*, c.name AS test_case_name
        FROM ai_test_case_runs r
        LEFT JOIN ai_test_cases c ON c.id = r.test_case_id
        WHERE r.status IN ('failed', 'error')
        ORDER BY r.id DESC LIMIT 20
        """
    )
    for row in test_rows:
        comparison = json_or_empty(row["comparison_json"])
        field = None
        for result in comparison.get("field_results") or []:
            if isinstance(result, dict) and result.get("passed") is False:
                field = result.get("field")
                break
        items.append({"timestamp": row["started_at"], "source_type": "test_case", "endpoint": row["endpoint"], "environment_code": row["environment_code"], "field": field, "message": comparison.get("summary") or row["error_message"] or "Test case comparison failed.", "link_id": str(row["id"])})

    suite_rows = db_fetchall(
        """
        SELECT r.*, s.name AS suite_name
        FROM ai_test_suite_runs r
        LEFT JOIN ai_test_suites s ON s.suite_id = r.suite_id
        WHERE r.status IN ('failed', 'error')
        ORDER BY r.id DESC LIMIT 10
        """
    )
    for row in suite_rows:
        summary = json_or_empty(row["summary_json"])
        items.append({"timestamp": row["started_at"], "source_type": "suite", "endpoint": row["endpoint"], "environment_code": row["environment_code"], "field": None, "message": f"Suite {row['suite_name'] or row['suite_id']} status {row['status']} pass_rate={summary.get('pass_rate')}", "link_id": row["suite_run_id"]})

    comparison_rows = db_fetchall("SELECT * FROM ai_prompt_comparisons ORDER BY id DESC LIMIT 10")
    for row in comparison_rows:
        summary = json_or_empty(row["summary_json"])
        if int(summary.get("regressed") or 0) > 0 or int(summary.get("error") or 0) > 0:
            items.append({"timestamp": row["started_at"], "source_type": "comparison", "endpoint": row["endpoint"], "environment_code": row["environment_code"], "field": None, "message": f"Prompt comparison regressions={summary.get('regressed', 0)} errors={summary.get('error', 0)}", "link_id": row["comparison_id"]})
    items.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    return items[:limit]


def build_regression_dashboard() -> dict[str, Any]:
    return {
        "required_suite_readiness": regression_required_suite_readiness(),
        "latest_suite_runs": regression_latest_suite_runs(),
        "recent_prompt_comparisons": regression_recent_prompt_comparisons(),
        "recent_promotions": regression_recent_promotions(),
        "workflow_summary": regression_workflow_summary(),
        "top_failing_fields": regression_top_failing_fields(),
        "recent_validation_failures": regression_recent_validation_failures(),
    }
