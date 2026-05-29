"""Workflow run and step trace helpers."""

import json
import secrets
import time
from typing import Any

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


def start_workflow_run(
    endpoint: str,
    environment_code: str | None = None,
    user_id: int | None = None,
    api_key_id: str | None = None,
    source: str | None = None,
) -> str:
    run_id = f"run_{time.strftime('%Y%m%d_%H%M%S', time.gmtime())}_{secrets.token_hex(4)}"
    db_execute(
        """
        INSERT INTO workflow_runs
        (run_id, endpoint, environment_code, user_id, api_key_id, source, status, started_at)
        VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
        """,
        (run_id, endpoint, environment_code, user_id, api_key_id, source, now_text()),
    )
    return run_id


def finish_workflow_run(run_id: str, status: str, error_message: str | None = None) -> None:
    row = db_fetchone("SELECT started_at FROM workflow_runs WHERE run_id = ?", (run_id,))
    finished_at = now_text()
    started = parse_timestamp(row["started_at"] if row else None)
    finished = parse_timestamp(finished_at)
    duration_ms = int(max(0, (finished - started) * 1000)) if started and finished else None
    db_execute(
        "UPDATE workflow_runs SET status = ?, finished_at = ?, duration_ms = ?, error_message = ? WHERE run_id = ?",
        (status, finished_at, duration_ms, error_message, run_id),
    )
    cleanup_workflow_runs()


def start_workflow_step(
    run_id: str,
    step_name: str,
    step_order: int,
    model: str | None = None,
    prompt_version: str | None = None,
    input_summary: str | None = None,
) -> int:
    with DB_LOCK:
        with db_connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO workflow_run_steps
                (run_id, step_name, step_order, status, model, prompt_version, started_at, input_summary)
                VALUES (?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (run_id, step_name, step_order, model, prompt_version, now_text(), input_summary),
            )
            conn.commit()
            return int(cursor.lastrowid)


def finish_workflow_step(
    step_id: int,
    status: str = "passed",
    output_summary: str | None = None,
    output_json: Any | None = None,
    error_message: str | None = None,
) -> None:
    row = db_fetchone("SELECT started_at FROM workflow_run_steps WHERE id = ?", (step_id,))
    finished_at = now_text()
    started = parse_timestamp(row["started_at"] if row else None)
    finished = parse_timestamp(finished_at)
    duration_ms = int(max(0, (finished - started) * 1000)) if started and finished else None
    db_execute(
        """
        UPDATE workflow_run_steps
        SET status = ?, finished_at = ?, duration_ms = ?, output_summary = ?, output_json = ?, error_message = ?
        WHERE id = ?
        """,
        (status, finished_at, duration_ms, output_summary, safe_json(output_json), error_message, step_id),
    )


def fail_workflow_step(step_id: int, error_message: str) -> None:
    finish_workflow_step(step_id, status="failed", error_message=error_message)


def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    run = db_fetchone("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,))
    if not run:
        return None
    steps = db_fetchall("SELECT * FROM workflow_run_steps WHERE run_id = ? ORDER BY step_order, id", (run_id,))
    llm_calls = db_fetchall("SELECT * FROM llm_call_events WHERE run_id = ? ORDER BY id", (run_id,))
    result = dict(run)
    result["steps"] = [dict(step) for step in steps]
    result["llm_calls"] = [dict(call) for call in llm_calls]
    for step in result["steps"]:
        if step.get("output_json"):
            try:
                step["output_json"] = json.loads(step["output_json"])
            except json.JSONDecodeError:
                pass
    return result


def record_llm_call_event(
    *,
    run_id: str | None,
    agent_name: str,
    model: str,
    temperature: float | None,
    response_format: str | None,
    timeout_seconds: int | None,
    duration_ms: float,
    status: str,
    json_parse_status: str | None = None,
) -> None:
    db_execute(
        """
        INSERT INTO llm_call_events
        (timestamp, run_id, agent_name, model, temperature, response_format, timeout_seconds, duration_ms, status, json_parse_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_text(),
            run_id,
            agent_name,
            model,
            temperature,
            response_format,
            timeout_seconds,
            duration_ms,
            status,
            json_parse_status,
        ),
    )


def update_latest_llm_call_json_parse_status(
    *,
    run_id: str | None,
    agent_name: str,
    json_parse_status: str,
) -> None:
    if not run_id:
        return
    db_execute(
        """
        UPDATE llm_call_events
        SET json_parse_status = ?
        WHERE id = (
            SELECT id FROM llm_call_events
            WHERE run_id = ?
                AND agent_name = ?
                AND (json_parse_status = 'pending' OR json_parse_status IS NULL)
            ORDER BY id DESC
            LIMIT 1
        )
        """,
        (json_parse_status, run_id, agent_name),
    )


def list_workflow_runs(
    endpoint: str | None = None,
    environment_code: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("endpoint = ?")
        params.append(endpoint)
    if environment_code:
        filters.append("environment_code = ?")
        params.append(environment_code.upper())
    if status:
        filters.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(f"SELECT * FROM workflow_runs {where} ORDER BY id DESC LIMIT ?", tuple(params))
    return [dict(row) for row in rows]


def cleanup_workflow_runs(keep_latest: int = 1000) -> None:
    db_execute(
        """
        DELETE FROM intake_metadata_reviews
        WHERE run_id IN (
            SELECT run_id FROM workflow_runs
            WHERE id NOT IN (
                SELECT id FROM workflow_runs ORDER BY id DESC LIMIT ?
            )
        )
        """,
        (keep_latest,),
    )
    db_execute(
        """
        DELETE FROM workflow_run_steps
        WHERE run_id IN (
            SELECT run_id FROM workflow_runs
            WHERE id NOT IN (
                SELECT id FROM workflow_runs ORDER BY id DESC LIMIT ?
            )
        )
        """,
        (keep_latest,),
    )
    db_execute(
        """
        DELETE FROM workflow_runs
        WHERE id NOT IN (
            SELECT id FROM workflow_runs ORDER BY id DESC LIMIT ?
        )
        """,
        (keep_latest,),
    )
