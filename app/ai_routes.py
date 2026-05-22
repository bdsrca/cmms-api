"""Controlled CMMS AI endpoint route registration."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from .ai_endpoints import (
    cmms_assistant as cmms_assistant_helper,
    cmms_intake as cmms_intake_helper,
    extract_work_order_fields as extract_work_order_fields_helper,
    summarize_work_order as summarize_work_order_helper,
)
from .api_keys import require_api_key
from .email_intake import build_email_intake_text


def build_ai_router(
    *,
    call_ollama: Callable[..., Any],
    text_request_model: type[Any],
    summary_response_model: type[Any],
    assistant_response_model: type[Any],
    extract_fields_request_model: type[Any],
    extract_fields_response_model: type[Any],
    email_intake_request_model: type[Any],
    intake_response_model: type[Any],
) -> APIRouter:
    router = APIRouter()
    TextRequest = text_request_model
    ExtractFieldsRequest = extract_fields_request_model
    EmailIntakeRequest = email_intake_request_model

    @router.post(
        "/api/ai/summarize-work-order",
        response_model=summary_response_model,
        dependencies=[Depends(require_api_key)],
    )
    async def summarize_work_order(request: Request, payload: TextRequest) -> Any:
        if payload.environment_code:
            request.state.environment_code = payload.environment_code
        return await summarize_work_order_helper(payload, call_ollama_func=call_ollama)

    @router.post(
        "/api/ai/cmms-assistant",
        response_model=assistant_response_model,
        dependencies=[Depends(require_api_key)],
    )
    async def cmms_assistant(request: Request, payload: TextRequest) -> Any:
        if payload.environment_code:
            request.state.environment_code = payload.environment_code
        return await cmms_assistant_helper(payload, call_ollama_func=call_ollama)

    @router.post(
        "/api/ai/extract-work-order-fields",
        response_model=extract_fields_response_model,
        dependencies=[Depends(require_api_key)],
    )
    async def extract_work_order_fields(request: Request, payload: ExtractFieldsRequest) -> Any:
        result = await extract_work_order_fields_helper(payload, call_ollama_func=call_ollama)
        env_code = result.pop("_environment_code", None)
        if env_code:
            request.state.environment_code = env_code
        return result

    @router.post(
        "/api/ai/cmms-intake",
        response_model=intake_response_model,
        dependencies=[Depends(require_api_key)],
    )
    async def cmms_intake(request: Request, payload: ExtractFieldsRequest) -> Any:
        result = await cmms_intake_helper(
            payload,
            user_id=getattr(request.state, "user_id", None),
            api_key_id=getattr(request.state, "api_key_id", None),
            call_ollama_func=call_ollama,
        )
        if result.get("environment_code"):
            request.state.environment_code = result["environment_code"]
        return result

    @router.post(
        "/api/ai/intake/email",
        response_model=intake_response_model,
        dependencies=[Depends(require_api_key)],
    )
    async def email_intake(request: Request, payload: EmailIntakeRequest) -> Any:
        text = build_email_intake_text(
            from_email=payload.from_email,
            to_email=payload.to_email,
            subject=payload.subject,
            body=payload.body,
        )
        if len(text) > 4000:
            raise HTTPException(
                status_code=422,
                detail="Email intake content must be 4000 characters or fewer after formatting",
            )
        intake_payload = ExtractFieldsRequest(
            text=text,
            environment_code=payload.environment_code,
            source="email_api",
        )
        result = await cmms_intake_helper(
            intake_payload,
            user_id=getattr(request.state, "user_id", None),
            api_key_id=getattr(request.state, "api_key_id", None),
            source="email_api",
            call_ollama_func=call_ollama,
        )
        if result.get("environment_code"):
            request.state.environment_code = result["environment_code"]
        return result

    return router
