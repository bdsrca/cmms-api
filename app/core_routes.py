"""Low-risk core and portal routes."""

from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from .config import MODEL_NAME, SERVICE_NAME
from .offline_ui import render_offline_html, render_offline_service_worker
from .security import PortalUser, current_user
from .ui import render_portal_html


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str


class PublicDocumentationItem(BaseModel):
    slug: str
    title: str
    summary: str
    sections: list[str]


class PublicAvailabilityResponse(BaseModel):
    service: str
    model: str
    api_available: bool
    model_available: bool


PUBLIC_DOCUMENTATION: tuple[PublicDocumentationItem, ...] = (
    PublicDocumentationItem(
        slug="overview",
        title="Operator Console Overview",
        summary="A read-only orientation to the local CMMS advisory console.",
        sections=[
            "The portal helps operators test intake, validation, draft generation, and handoff readiness before any controlled CMMS action.",
            "Guest documentation does not create a portal session and cannot call operator, admin, AI, system, or CMMS connector endpoints.",
        ],
    ),
    PublicDocumentationItem(
        slug="security-boundary",
        title="Security Boundary",
        summary="What remains protected when someone browses documentation.",
        sections=[
            "API keys, users, logs, system controls, environment configuration, prompt management, and KB status require an authenticated portal session.",
            "CMMS write-back remains gated by deterministic validation, safety review, handoff readiness, and explicit connector enablement.",
        ],
    ),
    PublicDocumentationItem(
        slug="api-usage",
        title="API Usage Model",
        summary="How controlled API access is expected to work after sign-in.",
        sections=[
            "Generated API keys are for advisory AI endpoints only and do not grant admin portal access.",
            "Clients should call the documented intake endpoints rather than any generic chat or direct model endpoint.",
        ],
    ),
    PublicDocumentationItem(
        slug="validation",
        title="Validation And Review",
        summary="How extracted work order data is checked before use.",
        sections=[
            "Server-side rules validate request type, building, room, priority, missing fields, review requirements, and advisory state.",
            "LLM output is advisory and must pass deterministic validation before downstream use.",
        ],
    ),
    PublicDocumentationItem(
        slug="voice-email-intake",
        title="Voice And Email Intake",
        summary="How operators can test alternate intake channels after authentication.",
        sections=[
            "Voice and pasted email workflows feed the same controlled advisory endpoints used by text intake.",
            "No email is sent automatically, and no work order is created from guest documentation access.",
        ],
    ),
)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, model=MODEL_NAME)


@router.get("/ui", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    return HTMLResponse(render_portal_html())


@router.get("/offline", response_class=HTMLResponse)
async def offline() -> HTMLResponse:
    return HTMLResponse(render_offline_html(PUBLIC_DOCUMENTATION))


@router.get("/offline-sw.js")
async def offline_service_worker() -> Response:
    return Response(
        render_offline_service_worker(),
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/api/public/documentation", response_model=list[PublicDocumentationItem])
async def public_documentation() -> list[PublicDocumentationItem]:
    return list(PUBLIC_DOCUMENTATION)


@router.get("/api/public/status", response_model=PublicAvailabilityResponse)
async def public_status() -> PublicAvailabilityResponse:
    return PublicAvailabilityResponse(
        service=SERVICE_NAME,
        model=MODEL_NAME,
        api_available=True,
        model_available=await local_model_available(),
    )


async def local_model_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True


@router.get("/api/me")
async def me(user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return user.model_dump()


@router.get("/api/default-api-key")
async def default_api_key(user: PortalUser = Depends(current_user)) -> dict[str, str]:
    return {"api_key": ""}


@router.get("/api/kb/status")
async def kb_status(user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return {
        "status": "placeholder",
        "message": "Knowledge base sources, indexing, and retrieval testing will be added in a future version.",
        "planned_interfaces": ["sources", "indexes", "retrieval_test"],
    }
