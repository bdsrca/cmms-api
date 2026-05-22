"""Prompt version, comparison, and promotion route registration."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .config import ALLOWED_REQUEST_TYPES, MODEL_NAME
from .prompt_comparisons import (
    get_prompt_comparison as get_prompt_comparison_helper,
    list_prompt_comparisons as list_prompt_comparisons_helper,
    run_prompt_comparison as run_prompt_comparison_helper,
)
from .prompt_promotions import (
    check_prompt_promotion_gate,
    get_prompt_promotion as get_prompt_promotion_helper,
    list_prompt_promotions as list_prompt_promotions_helper,
)
from .prompts import (
    activate_prompt_version as activate_prompt_version_helper,
    active_prompt_info,
    archive_prompt_version as archive_prompt_version_helper,
    create_prompt_version as create_prompt_version_helper,
    list_prompt_versions as list_prompt_versions_helper,
    list_prompt_versions_for_endpoint as list_prompt_versions_for_endpoint_helper,
    patch_prompt_version as patch_prompt_version_helper,
    prompt_version_by_id,
    test_prompt_version as test_prompt_version_helper,
)
from .security import PortalUser, current_admin, current_user


class PromptVersionRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=80)
    version: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    system_prompt: str = Field(..., min_length=1)
    user_template: str = Field(default="{{text}}", min_length=1)
    model: str = Field(default=MODEL_NAME, min_length=1, max_length=80)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")


class PromptVersionPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_prompt: str | None = Field(default=None, min_length=1)
    user_template: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1, max_length=80)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class PromptTestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None


class PromotionCheckRequest(BaseModel):
    comparison_id: str | None = None


class PromptActivationRequest(BaseModel):
    comparison_id: str | None = None
    override: bool = False
    override_reason: str | None = None


class PromptComparisonRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=80)
    environment_code: str | None = None
    baseline_prompt_id: int
    candidate_prompt_id: int
    enabled_only: bool = True


def build_prompt_router(
    *,
    call_ollama: Callable[..., Any],
    get_environment_values: Callable[..., Any],
    run_test_case_row_for_prompt_comparison: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/prompt-versions/active/{endpoint}")
    async def read_active_prompt_info(endpoint: str, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
        return active_prompt_info(endpoint)

    @router.get("/api/admin/prompt-versions")
    async def list_prompt_versions(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
        return list_prompt_versions_helper()

    @router.get("/api/admin/prompt-versions/{endpoint}")
    async def list_prompt_versions_for_endpoint(endpoint: str, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
        return list_prompt_versions_for_endpoint_helper(endpoint)

    @router.post("/api/admin/prompt-versions")
    async def create_prompt_version(payload: PromptVersionRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return create_prompt_version_helper(payload, user)

    @router.patch("/api/admin/prompt-versions/{prompt_id}")
    async def patch_prompt_version(
        prompt_id: int,
        payload: PromptVersionPatchRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return patch_prompt_version_helper(prompt_id, payload, user)

    @router.post("/api/admin/prompt-versions/{prompt_id}/promotion-check")
    async def prompt_promotion_check(
        prompt_id: int,
        payload: PromotionCheckRequest | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return check_prompt_promotion_gate(prompt_id, payload.comparison_id if payload else None)

    @router.post("/api/admin/prompt-versions/{prompt_id}/activate")
    async def activate_prompt_version(
        prompt_id: int,
        payload: PromptActivationRequest | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return activate_prompt_version_helper(prompt_id, payload, user, PromptActivationRequest)

    @router.post("/api/admin/prompt-versions/{prompt_id}/archive")
    async def archive_prompt_version(prompt_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return archive_prompt_version_helper(prompt_id, user)

    @router.post("/api/admin/prompt-versions/{prompt_id}/test")
    async def test_prompt_version(
        prompt_id: int,
        payload: PromptTestRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await test_prompt_version_helper(
            prompt_id,
            payload,
            allowed_request_types=ALLOWED_REQUEST_TYPES,
            get_environment_values=get_environment_values,
            call_ollama=call_ollama,
        )

    @router.post("/api/admin/prompt-comparisons")
    async def create_prompt_comparison(
        payload: PromptComparisonRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await run_prompt_comparison_helper(
            payload,
            user,
            prompt_version_by_id=prompt_version_by_id,
            run_test_case_row=run_test_case_row_for_prompt_comparison,
        )

    @router.get("/api/admin/prompt-comparisons")
    async def list_prompt_comparisons(
        endpoint: str | None = None,
        status: str | None = None,
        limit: int = 50,
        user: PortalUser = Depends(current_admin),
    ) -> list[dict[str, Any]]:
        return list_prompt_comparisons_helper(endpoint=endpoint, status=status, limit=limit)

    @router.get("/api/admin/prompt-comparisons/{comparison_id}")
    async def get_prompt_comparison(comparison_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        item = get_prompt_comparison_helper(comparison_id)
        if not item:
            raise HTTPException(status_code=404, detail="Prompt comparison not found")
        return item

    @router.get("/api/admin/prompt-promotions")
    async def list_prompt_promotions(
        endpoint: str | None = None,
        limit: int = 50,
        user: PortalUser = Depends(current_admin),
    ) -> list[dict[str, Any]]:
        return list_prompt_promotions_helper(endpoint=endpoint, limit=limit)

    @router.get("/api/admin/prompt-promotions/{promotion_id}")
    async def get_prompt_promotion(promotion_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        item = get_prompt_promotion_helper(promotion_id)
        if not item:
            raise HTTPException(status_code=404, detail="Prompt promotion not found")
        return item

    return router
