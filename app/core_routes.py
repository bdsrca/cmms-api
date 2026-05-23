"""Low-risk core and portal routes."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import MODEL_NAME, SERVICE_NAME
from .security import PortalUser, current_user
from .ui import render_portal_html


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, model=MODEL_NAME)


@router.get("/ui", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    return HTMLResponse(render_portal_html())


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
