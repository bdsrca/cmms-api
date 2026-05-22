"""Operational logs, workflow trace, reporting, and regression routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .db import LOG_FILE, db_fetchall
from .regression_dashboard import build_regression_dashboard
from .security import PortalUser, current_admin, current_user
from .intake_metadata_reviews import apply_saved_metadata_review, metadata_review_record
from .intake_handoff import build_cmms_handoff_candidate
from .workflow_trace import get_workflow_run, list_workflow_runs


router = APIRouter()


class LogResponse(BaseModel):
    log_file: str
    lines: list[str]


class MetadataReviewApplyRequest(BaseModel):
    submitted_by: str | None = Field(default=None, max_length=160)
    submitted_email: str | None = Field(default=None, max_length=320)
    submitted_phone: str | None = Field(default=None, max_length=80)
    requested_due: str | None = Field(default=None, max_length=40)
    building: str | None = Field(default=None, max_length=80)
    room: str | None = Field(default=None, max_length=80)


def read_log_lines(line_count: int) -> list[str]:
    safe_count = max(1, min(line_count, 1000))
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as log_file:
        return [line.rstrip("\r\n") for line in log_file.readlines()[-safe_count:]]


@router.get("/api/admin/regression-dashboard")
async def regression_dashboard(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return build_regression_dashboard()


@router.get("/api/admin/logs", response_model=LogResponse)
async def admin_logs(lines: int = 200, user: PortalUser = Depends(current_user)) -> LogResponse:
    return LogResponse(log_file=str(LOG_FILE), lines=read_log_lines(lines))


@router.get("/api/admin/workflow-runs")
async def admin_workflow_runs(
    endpoint: str | None = None,
    environment_code: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_workflow_runs(endpoint=endpoint, environment_code=environment_code, status=status, limit=limit)


@router.get("/api/admin/workflow-runs/{run_id}")
async def admin_workflow_run_detail(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    run = get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    review = metadata_review_record(run_id)
    if review:
        run["metadata_review"] = review
    return run


@router.get("/api/admin/workflow-runs/{run_id}/metadata-review")
async def workflow_run_metadata_review(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    review = metadata_review_record(run_id)
    if not review:
        raise HTTPException(status_code=404, detail="Intake metadata review record not found")
    return review


@router.post("/api/admin/workflow-runs/{run_id}/metadata-review/apply")
async def apply_workflow_run_metadata_review(
    run_id: str,
    payload: MetadataReviewApplyRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    review = apply_saved_metadata_review(
        run_id,
        payload.model_dump(exclude_unset=True),
        reviewed_by_user_id=user.user_id,
    )
    if not review:
        raise HTTPException(status_code=404, detail="Intake metadata review record not found")
    return review


@router.get("/api/admin/workflow-runs/{run_id}/cmms-handoff-candidate")
async def workflow_run_cmms_handoff_candidate(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    run = get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    review = metadata_review_record(run_id)
    if not review:
        raise HTTPException(status_code=404, detail="Intake metadata review record not found")
    if not review.get("metadata_review", {}).get("reviewed"):
        raise HTTPException(status_code=409, detail="Metadata review must be applied before CMMS handoff candidate generation")
    candidate = build_cmms_handoff_candidate(run, review)
    if not candidate:
        raise HTTPException(status_code=409, detail="Workflow run does not contain handoff candidate extraction fields")
    return candidate


@router.get("/api/admin/reports/usage")
async def usage_report(user: PortalUser = Depends(current_user)) -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT endpoint, status_code, COALESCE(key_name, 'none') AS key_name,
               COALESCE(environment_code, '') AS environment_code,
               COUNT(*) AS calls, ROUND(AVG(duration_ms), 1) AS avg_duration_ms
        FROM usage_events
        GROUP BY endpoint, status_code, key_name, environment_code
        ORDER BY calls DESC, endpoint
        LIMIT 100
        """
    )
    return [dict(row) for row in rows]
