"""Admin routes for CMMS connector configuration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .cmms_connectors import (
    cmms_push_gate,
    dry_run_cmms_connector_mapping,
    get_cmms_connector,
    list_cmms_push_events,
    probe_cmms_connector,
    public_cmms_connector,
    upsert_cmms_connector,
)
from .security import PortalUser, current_admin


router = APIRouter()


class CmmsConnectorRequest(BaseModel):
    enabled: bool = False
    auto_push_enabled: bool = False
    endpoint_url: str | None = Field(default=None, max_length=500)
    auth_type: str = Field(default="bearer", pattern="^(bearer|header)$")
    auth_header_name: str | None = Field(default=None, max_length=120)
    secret_value: str | None = Field(default=None, max_length=2000)
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    http_method: str = Field(default="POST", pattern="^(POST|PUT|PATCH)$")
    success_status_codes: str = Field(default="200,201,202", max_length=80)
    external_id_path: str | None = Field(default=None, max_length=160)
    dry_run_enabled: bool = False
    require_metadata_review: bool = False
    static_headers: dict[str, str] = Field(default_factory=dict)
    payload_root_key: str | None = Field(default=None, max_length=80)
    auto_push_note: str | None = Field(default=None, max_length=240)
    field_mappings: list[dict[str, Any]] | dict[str, str] | None = None


class CmmsConnectorDryRunRequest(BaseModel):
    canonical_payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/admin/environments/{environment_code}/cmms-connector")
async def get_environment_cmms_connector(
    environment_code: str,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    return public_cmms_connector(get_cmms_connector(environment_code))


@router.put("/api/admin/environments/{environment_code}/cmms-connector")
async def put_environment_cmms_connector(
    environment_code: str,
    payload: CmmsConnectorRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    try:
        connector = upsert_cmms_connector(environment_code, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return public_cmms_connector(connector)


@router.post("/api/admin/environments/{environment_code}/cmms-connector/test")
async def test_environment_cmms_connector(
    environment_code: str,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    connector = get_cmms_connector(environment_code)
    status, reasons = cmms_push_gate(
        connector,
        {
            "contract_valid": True,
            "ai_validation_valid": True,
            "can_create_work_order": True,
            "human_review_required": False,
            "handoff_status": "ready",
        },
        {"test": True},
    )
    return {
        "status": "ready" if status == "allowed" else status,
        "blocked_reasons": reasons,
        "connector": public_cmms_connector(connector),
    }


@router.post("/api/admin/environments/{environment_code}/cmms-connector/probe")
async def probe_environment_cmms_connector(
    environment_code: str,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    return probe_cmms_connector(environment_code)


@router.post("/api/admin/environments/{environment_code}/cmms-connector/dry-run")
async def dry_run_environment_cmms_connector(
    environment_code: str,
    payload: CmmsConnectorDryRunRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    try:
        return dry_run_cmms_connector_mapping(environment_code, payload.canonical_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/admin/environments/{environment_code}/cmms-connector/push-events")
async def get_environment_cmms_connector_push_events(
    environment_code: str,
    limit: int = 25,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_cmms_push_events(environment_code, limit=limit)
