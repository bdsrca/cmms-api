"""Environment and code-list route registration."""

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .environments import (
    create_environment as create_environment_helper,
    import_codes as import_codes_helper,
    list_codes as list_codes_helper,
    list_environments as list_environments_helper,
    patch_code_value as patch_code_value_helper,
    patch_environment as patch_environment_helper,
    preview_codes as preview_codes_helper,
)
from .demo_environment import seed_demo_environment
from .security import PortalUser, current_admin, current_user


router = APIRouter()


class EnvironmentRequest(BaseModel):
    environment_code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    enabled: bool = True
    default_workflow_mode: Literal["fast", "full"] = "fast"


class EnvironmentPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    default_workflow_mode: Literal["fast", "full"] | None = None


class CodeImportRequest(BaseModel):
    category: str
    values: list[str] | None = None
    text: str | None = None
    replace: bool = True


class CodeValuePatchRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=240)
    aliases: str | None = Field(default=None, max_length=500)
    metadata_json: str | None = None
    enabled: bool | None = None


@router.get("/api/environments")
async def list_environments(user: PortalUser = Depends(current_user)) -> list[dict[str, Any]]:
    return list_environments_helper()


@router.post("/api/admin/environments")
async def create_environment(payload: EnvironmentRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return create_environment_helper(payload)


@router.patch("/api/admin/environments/{environment_code}")
async def patch_environment(environment_code: str, payload: EnvironmentPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return patch_environment_helper(environment_code, payload)


@router.post("/api/admin/environments/{environment_code}/demo-setup")
async def load_demo_setup(environment_code: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return seed_demo_environment(environment_code)


@router.get("/api/admin/environments/{environment_code}/codes")
async def list_codes(environment_code: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return list_codes_helper(environment_code)


@router.post("/api/admin/environments/{environment_code}/codes/preview")
async def preview_codes(environment_code: str, payload: CodeImportRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return preview_codes_helper(environment_code, payload)


@router.post("/api/admin/environments/{environment_code}/codes/import")
async def import_codes(environment_code: str, payload: CodeImportRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return import_codes_helper(environment_code, payload)


@router.patch("/api/admin/environments/{environment_code}/codes/{code_id}")
async def patch_code_value(
    environment_code: str,
    code_id: int,
    payload: CodeValuePatchRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    return patch_code_value_helper(environment_code, code_id, payload)
