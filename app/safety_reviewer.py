"""Safety reviewer agent helpers for controlled CMMS intake workflows."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from .prompts import prompt_messages

REVIEW_SOURCE = "safety_reviewer_agent"
ALLOWED_REVIEW_STATUSES = {"pass", "warning", "fail"}
MAX_REVIEW_ITEMS = 8
MAX_REVIEW_TEXT_LENGTH = 240

ReviewerCaller = Callable[..., Awaitable[str]]


def clean_review_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    if not text:
        return None
    if len(text) > MAX_REVIEW_TEXT_LENGTH:
        return text[: MAX_REVIEW_TEXT_LENGTH - 3] + "..."
    return text


def normalize_reviewer_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_review_text(item)
        if text and text not in seen:
            normalized.append(text)
            seen.add(text)
        if len(normalized) >= MAX_REVIEW_ITEMS:
            break
    return normalized


def normalize_reviewer_status(value: Any) -> str:
    status = value.strip().lower() if isinstance(value, str) else ""
    return status if status in ALLOWED_REVIEW_STATUSES else "warning"


def normalize_reviewer_output(data: dict[str, Any]) -> dict[str, Any]:
    human_review_recommended = data.get("human_review_recommended")
    return {
        "enabled": True,
        "status": normalize_reviewer_status(data.get("status")),
        "human_review_recommended": human_review_recommended if isinstance(human_review_recommended, bool) else False,
        "risk_flags": normalize_reviewer_list(data.get("risk_flags")),
        "notes": normalize_reviewer_list(data.get("notes")),
        "source": REVIEW_SOURCE,
    }


def skipped_reviewer_block(message: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "skipped",
        "human_review_recommended": False,
        "risk_flags": [],
        "notes": [],
        "source": REVIEW_SOURCE,
        "message": message,
    }


def failed_reviewer_block(message: str) -> dict[str, Any]:
    note = clean_review_text(message) or "Safety reviewer failed."
    return {
        "enabled": True,
        "status": "fail",
        "human_review_recommended": False,
        "risk_flags": ["reviewer_failed"],
        "notes": [note],
        "source": REVIEW_SOURCE,
    }


def reviewer_context_json(
    *,
    result: dict[str, Any],
    contract: dict[str, Any],
    ai_validation: dict[str, Any],
    drafts: dict[str, Any],
) -> str:
    context = {
        "advisory_mode": {
            "cmms_write_back": False,
            "work_order_created": False,
            "email_sent": False,
            "reviewer_can_modify_fields": False,
        },
        "result": result,
        "contract": contract,
        "environment_validation": ai_validation,
        "drafts": drafts,
    }
    return json.dumps(context, ensure_ascii=True, default=str)


async def run_safety_reviewer_agent(
    *,
    result: dict[str, Any],
    contract: dict[str, Any],
    ai_validation: dict[str, Any],
    drafts: dict[str, Any],
    call_ollama_func: ReviewerCaller,
    prompt_id: int | None = None,
    timeout: int = 45,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context_json = reviewer_context_json(
        result=result,
        contract=contract,
        ai_validation=ai_validation,
        drafts=drafts,
    )
    endpoint = "cmms-intake-reviewer"
    messages, prompt_meta = prompt_messages(endpoint, {"context_json": context_json}, prompt_id)
    prompt_meta = {**prompt_meta, "endpoint": endpoint}
    try:
        content = await call_ollama_func(
            messages,
            timeout=timeout,
            temperature=prompt_meta["temperature"],
            model=prompt_meta["model"],
        )
        parsed = json.loads(content.strip())
    except json.JSONDecodeError:
        return failed_reviewer_block("Safety reviewer returned invalid JSON"), prompt_meta
    if not isinstance(parsed, dict):
        return failed_reviewer_block("Safety reviewer returned invalid JSON"), prompt_meta
    return normalize_reviewer_output(parsed), prompt_meta
