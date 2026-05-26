"""Controlled CMMS AI endpoint orchestration and Ollama call helpers."""

import hashlib
import json
import re
import threading
import time
from copy import deepcopy
from typing import Any, Awaitable, Callable

import httpx
from fastapi import HTTPException

from .asset_registry import build_work_order_plan, resolve_asset_context
from .cmms_action_plan import build_initial_action_plan, create_work_order_idempotency_key, finalize_action_plan
from .code_normalizer import (
    apply_code_normalization_suggestions,
    build_code_normalizer_context,
    collect_invalid_code_candidates,
    enabled_codes_by_field,
    failed_code_normalization_block,
    load_code_values_for_normalizer,
    normalize_code_normalizer_output,
    skipped_code_normalization_block,
)
from .cmms_connectors import auto_push_cmms_payload
from .config import (
    ADVISORY_WARNING,
    ALLOWED_REQUEST_TYPES,
    EXTRACTOR_MODEL_NAME,
    MODEL_NAME,
    OLLAMA_CHAT_URL,
)
from .db import db_execute
from .environments import default_workflow_mode, get_environment_values
from .intake_handoff import build_canonical_cmms_payload_preview, build_environment_handoff_preview
from .intake_metadata import build_intake_metadata, extract_metadata_from_text, unreviewed_metadata_review
from .intake_metadata_reviews import save_extracted_metadata_review
from .inventory_procurement import build_procurement_request, resolve_inventory_context
from .orchestration_summary import build_orchestration_summary
from .output_contracts import skipped_ai_validation, validate_output_contract
from .prompts import intake_prompt_messages, prompt_messages
from .safety_reviewer import run_safety_reviewer_agent, skipped_reviewer_block
from .technician_roster import apply_assignment_to_payload, resolve_assignment_context
from .validation_rules import validate_ai_output
from .workflow_trace import (
    fail_workflow_step,
    finish_workflow_run,
    finish_workflow_step,
    start_workflow_run,
    start_workflow_step,
)

OllamaCaller = Callable[..., Awaitable[str]]

FAST_EXTRACTION_CACHE_TTL_SECONDS = 10 * 60
FAST_EXTRACTION_CACHE_MAX_ENTRIES = 128
FAST_EXTRACTION_CACHE_VERSION = "canonical_tokens_v1"
_FAST_EXTRACTION_CACHE: dict[str, dict[str, Any]] = {}
_FAST_EXTRACTION_CACHE_LOCK = threading.Lock()

_CANONICAL_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "can",
    "could",
    "for",
    "i",
    "in",
    "is",
    "it",
    "kindly",
    "of",
    "on",
    "please",
    "room",
    "that",
    "the",
    "this",
    "to",
    "we",
    "with",
    "would",
    "you",
}
_CANONICAL_SYNONYMS = {
    "ticket": "workorder",
    "wo": "workorder",
}


def clear_fast_extraction_cache() -> None:
    with _FAST_EXTRACTION_CACHE_LOCK:
        _FAST_EXTRACTION_CACHE.clear()


def canonicalize_fast_cache_text(text: str) -> str:
    normalized = str(text or "").casefold()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"\bw\s*/\s*o\b", " workorder ", normalized)
    normalized = re.sub(r"\bwork\s+order\b", " workorder ", normalized)
    normalized = re.sub(r"\bhigh\s+priority\b", " urgent ", normalized)
    normalized = re.sub(r"\bair\s+handler\s+unit\s*(\d+)\b", r" ahu\1 ", normalized)
    normalized = re.sub(r"\bair\s+handler\s*(\d+)\b", r" ahu\1 ", normalized)
    normalized = re.sub(r"\b([a-z]+)\s*[-#/]\s*(\d+)\b", r"\1\2", normalized)
    normalized = re.sub(
        r"\b(ahu|mech|room|fcu|pump|panel|zone|tech)\s+(\d+)\b",
        r"\1\2",
        normalized,
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    tokens = []
    for token in normalized.split():
        token = _CANONICAL_SYNONYMS.get(token, token)
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if token and token not in _CANONICAL_STOPWORDS:
            tokens.append(token)
    return " ".join(sorted(tokens))


def fast_extraction_cache_key(
    *,
    text: str,
    environment_code: str | None,
    prompt_meta: dict[str, Any],
    valid_buildings: list[str],
    valid_priorities: list[str],
) -> tuple[str, str]:
    canonical_text = canonicalize_fast_cache_text(text)
    key_payload = {
        "version": FAST_EXTRACTION_CACHE_VERSION,
        "environment_code": str(environment_code or "").upper(),
        "prompt_id": prompt_meta.get("prompt_id"),
        "prompt_version": prompt_meta.get("prompt_version"),
        "model": prompt_meta.get("model"),
        "temperature": prompt_meta.get("temperature"),
        "valid_buildings": sorted(valid_buildings),
        "valid_priorities": sorted(valid_priorities),
        "canonical_text": canonical_text,
    }
    key_hash = hashlib.sha256(json.dumps(key_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return key_hash, canonical_text


def _prune_fast_extraction_cache(now: float) -> None:
    expired = [key for key, entry in _FAST_EXTRACTION_CACHE.items() if entry["expires_at"] <= now]
    for key in expired:
        _FAST_EXTRACTION_CACHE.pop(key, None)
    if len(_FAST_EXTRACTION_CACHE) <= FAST_EXTRACTION_CACHE_MAX_ENTRIES:
        return
    ordered = sorted(_FAST_EXTRACTION_CACHE.items(), key=lambda item: item[1].get("last_used_at", 0))
    for key, _entry in ordered[: len(_FAST_EXTRACTION_CACHE) - FAST_EXTRACTION_CACHE_MAX_ENTRIES]:
        _FAST_EXTRACTION_CACHE.pop(key, None)


def read_fast_extraction_cache(key_hash: str) -> dict[str, Any] | None:
    now = time.time()
    with _FAST_EXTRACTION_CACHE_LOCK:
        _prune_fast_extraction_cache(now)
        entry = _FAST_EXTRACTION_CACHE.get(key_hash)
        if not entry:
            return None
        entry["last_used_at"] = now
        entry["hit_count"] = int(entry.get("hit_count") or 0) + 1
        return deepcopy(entry["data"])


def write_fast_extraction_cache(key_hash: str, data: dict[str, Any]) -> None:
    now = time.time()
    with _FAST_EXTRACTION_CACHE_LOCK:
        _prune_fast_extraction_cache(now)
        _FAST_EXTRACTION_CACHE[key_hash] = {
            "data": deepcopy(data),
            "created_at": now,
            "last_used_at": now,
            "expires_at": now + FAST_EXTRACTION_CACHE_TTL_SECONDS,
            "hit_count": 0,
        }


def fast_cache_block(status: str, key_hash: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "status": status,
        "match": "canonical",
        "key_hash": key_hash[:16],
        "ttl_seconds": FAST_EXTRACTION_CACHE_TTL_SECONDS,
        "canonicalizer": FAST_EXTRACTION_CACHE_VERSION,
    }


def build_cmms_intake_push_result(
    *,
    run_id: str,
    environment_code: str | None,
    payload: dict[str, Any],
    contract_valid: bool,
    ai_validation: dict[str, Any],
    validation: dict[str, Any],
    review: dict[str, Any],
    metadata_review: dict[str, Any] | None = None,
    workflow_mode: str = "full",
    sender: Any = None,
) -> dict[str, Any]:
    env_code = str(environment_code or "").strip().upper()
    canonical_preview = build_canonical_cmms_payload_preview(payload, run_id)
    environment_preview = build_environment_handoff_preview(canonical_preview, env_code)
    push_context = {
        "contract_valid": bool(contract_valid),
        "ai_validation_valid": ai_validation.get("valid") is True,
        "can_create_work_order": bool(validation.get("can_create_work_order")),
        "human_review_required": bool(validation.get("needs_human_review")) or bool(review.get("human_review_recommended")),
        "review_passed": review.get("status") == "pass",
        "metadata_reviewed": bool((metadata_review or {}).get("reviewed")),
        "handoff_status": (environment_preview or {}).get("status"),
        "fast_mode": workflow_mode == "fast",
        "idempotency_key": create_work_order_idempotency_key(run_id),
    }
    result = auto_push_cmms_payload(env_code, canonical_preview, push_context, sender=sender)
    result["handoff_status"] = push_context["handoff_status"]
    return result


def workflow_mode_for_payload(payload: Any) -> str:
    explicit_mode = getattr(payload, "workflow_mode", None)
    if explicit_mode in {"fast", "full"}:
        return str(explicit_mode)
    return default_workflow_mode(getattr(payload, "environment_code", None))


def fast_mode_reviewer_block() -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "pass",
        "human_review_recommended": False,
        "risk_flags": [],
        "notes": ["LLM safety reviewer skipped in fast mode. Use full mode before live CMMS write-back."],
        "source": "fast_mode_deterministic_review",
        "message": "Fast mode skipped the LLM safety reviewer; dry-run planning can continue.",
    }


def deterministic_fast_drafts(
    *,
    fields: dict[str, Any],
    result_payload: dict[str, Any],
    assignment_context: dict[str, Any],
    inventory_context: dict[str, Any],
    procurement_request: dict[str, Any],
) -> dict[str, str]:
    summary = str(fields.get("summary") or result_payload.get("summary") or "CMMS intake request")
    priority = str(result_payload.get("priority") or fields.get("priority") or "NORMAL")
    asset_code = (result_payload.get("work_order_plan") or {}).get("asset_code")
    assignment = assignment_context.get("assignment") if isinstance(assignment_context, dict) else {}
    technician = (assignment_context.get("technician") or {}).get("label") if isinstance(assignment_context, dict) else None
    assign_to = technician or (assignment or {}).get("assign_to")
    inventory_status = inventory_context.get("status") if isinstance(inventory_context, dict) else None
    procurement_status = procurement_request.get("status") if isinstance(procurement_request, dict) else None

    subject = f" for {asset_code}" if asset_code else ""
    assignment_text = f" Assignment target: {assign_to}." if assign_to else ""
    inventory_text = f" Inventory status: {inventory_status}." if inventory_status else ""
    procurement_text = f" Procurement status: {procurement_status}." if procurement_status else ""
    return {
        "draft_wo_description": f"{summary} Priority: {priority}.{assignment_text}",
        "internal_note": (
            f"Fast mode deterministic draft{subject}. {ADVISORY_WARNING}"
            f"{inventory_text}{procurement_text} Full safety review is required before live CMMS write-back."
        ),
        "client_reply": f"Your request has been captured for review.{assignment_text}{procurement_text}",
    }


def normalize_allowed_values(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def clean_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def normalize_missing_fields(fields: Any) -> list[str]:
    if not isinstance(fields, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, str):
            continue
        cleaned = field.strip()
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return normalized


def ensure_missing_field(missing_fields: list[str], field: str) -> None:
    if field not in missing_fields:
        missing_fields.append(field)


def parse_json_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Model returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="Model returned invalid JSON")
    return parsed


async def call_ollama(
    messages: list[dict[str, str]],
    timeout: int = 120,
    temperature: float | None = None,
    model: str = MODEL_NAME,
) -> str:
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(OLLAMA_CHAT_URL, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail="Ollama request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to Ollama") from exc
    try:
        data = response.json()
        content = data["message"]["content"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Ollama returned an unexpected response") from exc
    if not isinstance(content, str):
        raise HTTPException(status_code=502, detail="Ollama returned an unexpected response")
    return content.strip()


def extractor_model_name() -> str:
    return EXTRACTOR_MODEL_NAME


def resolve_validation_lists(request: Any) -> tuple[list[str], list[str], str | None]:
    if getattr(request, "environment_code", None):
        values = get_environment_values(request.environment_code)
        buildings = values.get("buildings") or []
        priorities = values.get("priorities") or ["NORMAL"]
        return buildings, priorities, request.environment_code
    if hasattr(request, "valid_buildings") or hasattr(request, "valid_priorities"):
        if not request.valid_buildings:
            raise HTTPException(status_code=422, detail="valid_buildings is required when environment_code is not provided")
        if not request.valid_priorities:
            raise HTTPException(status_code=422, detail="valid_priorities is required when environment_code is not provided")
        return request.valid_buildings, request.valid_priorities, None
    return [], [], None


def validate_extracted_fields(
    data: dict[str, Any],
    valid_buildings: list[str],
    valid_priorities: list[str],
) -> dict[str, Any]:
    allowed_buildings = set(normalize_allowed_values(valid_buildings))
    allowed_priorities = set(normalize_allowed_values(valid_priorities))
    raw_extracted_fields = {
        "request_type": data.get("request_type"),
        "building": clean_optional_text(data.get("building")),
        "room": clean_optional_text(data.get("room")),
        "priority": clean_optional_text(data.get("priority")),
        "summary": clean_optional_text(data.get("summary")) or "",
    }
    invalid_code_candidates: dict[str, Any] = {}

    request_type = data.get("request_type")
    if request_type not in ALLOWED_REQUEST_TYPES:
        request_type = "Unknown"

    building = raw_extracted_fields["building"]
    building = building or None

    room = raw_extracted_fields["room"]
    room = room or None

    priority = raw_extracted_fields["priority"]
    if priority not in allowed_priorities:
        if priority:
            invalid_code_candidates["priority"] = priority
        priority = "NORMAL"

    summary = raw_extracted_fields["summary"]

    missing_fields = normalize_missing_fields(data.get("missing_fields"))
    if not building or building not in allowed_buildings:
        building = None
        ensure_missing_field(missing_fields, "building")
    if not room:
        ensure_missing_field(missing_fields, "room")

    needs_human_review = bool(data.get("needs_human_review"))
    if not building or not room:
        needs_human_review = True

    validated_fields = {
        "request_type": request_type,
        "building": building,
        "room": room,
        "priority": priority or "NORMAL",
        "summary": summary,
    }

    return {
        "request_type": request_type,
        "building": building,
        "room": room,
        "priority": priority or "NORMAL",
        "summary": summary,
        "missing_fields": normalize_missing_fields(missing_fields),
        "needs_human_review": needs_human_review,
        "confidence": clamp_confidence(data.get("confidence")),
        "raw_extracted_fields": raw_extracted_fields,
        "validated_fields": validated_fields,
        "invalid_code_candidates": invalid_code_candidates,
    }


def validate_intake(
    request_type: str,
    confidence: Any,
    field_data: dict[str, Any],
    valid_buildings: list[str],
    valid_priorities: list[str],
) -> tuple[str, float, dict[str, Any], dict[str, Any], dict[str, Any]]:
    validated = validate_extracted_fields(
        {
            "request_type": request_type,
            "building": field_data.get("building"),
            "room": field_data.get("room"),
            "priority": field_data.get("priority"),
            "summary": field_data.get("summary"),
            "missing_fields": [],
            "needs_human_review": False,
            "confidence": confidence,
        },
        valid_buildings,
        valid_priorities,
    )
    errors: list[str] = []
    if validated["request_type"] == "Unknown":
        errors.append("request_type is Unknown")
    if not validated["building"]:
        errors.append("building is missing or invalid")
    if not validated["room"]:
        errors.append("room is missing")
    can_create_work_order = not errors
    fields = {
        "building": validated["building"],
        "room": validated["room"],
        "priority": validated["priority"],
        "summary": validated["summary"],
    }
    validation = {
        "can_create_work_order": can_create_work_order,
        "needs_human_review": not can_create_work_order,
        "missing_fields": validated["missing_fields"],
        "errors": errors,
        "warnings": [ADVISORY_WARNING],
    }
    extraction_context = {
        "raw_extracted_fields": validated.get("raw_extracted_fields", {}),
        "validated_fields": validated.get("validated_fields", {}),
        "invalid_code_candidates": validated.get("invalid_code_candidates", {}),
    }
    return validated["request_type"], validated["confidence"], fields, validation, extraction_context


def redacted_summary(text: str, max_len: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    cleaned = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email]", cleaned)
    cleaned = re.sub(r"\b(?:phone(?: number)?|telephone|mobile)\s*(?:is|:)?\s*[+()0-9][0-9+() .-]{2,79}", "phone [phone]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[+()0-9][0-9+() .-]{6,}\b", "[phone]", cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned


async def summarize_work_order(payload: Any, call_ollama_func: OllamaCaller = call_ollama) -> dict[str, Any]:
    messages, prompt_meta = prompt_messages("summarize-work-order", {"text": payload.text})
    summary = await call_ollama_func(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
    return {"summary": summary}


async def cmms_assistant(payload: Any, call_ollama_func: OllamaCaller = call_ollama) -> dict[str, Any]:
    messages, prompt_meta = prompt_messages("cmms-assistant", {"text": payload.text})
    content = await call_ollama_func(messages, temperature=prompt_meta["temperature"], model=extractor_model_name())
    return {
        "mode": "cmms-assistant",
        "response": content,
        "model": MODEL_NAME,
        "safety": {
            "advisory_only": True,
            "cmms_write_back": False,
            "work_order_created": False,
            "email_sent": False,
        },
    }


async def extract_work_order_fields(payload: Any, call_ollama_func: OllamaCaller = call_ollama) -> dict[str, Any]:
    valid_buildings, valid_priorities, env_code = resolve_validation_lists(payload)
    messages, prompt_meta = prompt_messages(
        "extract-work-order-fields",
        {
            "text": payload.text,
            "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
            "valid_buildings": valid_buildings,
            "valid_priorities": valid_priorities,
        },
    )
    content = await call_ollama_func(messages, temperature=prompt_meta["temperature"], model=extractor_model_name())
    data = parse_json_response(content)
    result = validate_extracted_fields(data, valid_buildings, valid_priorities)
    return result | {"_environment_code": env_code}


async def execute_ai_endpoint_for_test(
    endpoint: str,
    input_text: str,
    environment_code: str | None,
    source: str = "test_case",
    prompt_id: int | None = None,
    reviewer_prompt_id: int | None = None,
    request_factory: Callable[..., Any] | None = None,
    call_ollama_func: OllamaCaller = call_ollama,
) -> dict[str, Any]:
    if endpoint == "summarize-work-order":
        messages, meta = prompt_messages(endpoint, {"text": input_text}, prompt_id)
        summary = await call_ollama_func(messages, temperature=meta["temperature"], model=meta["model"])
        return {"summary": summary, "prompt": meta}
    if endpoint == "cmms-assistant":
        messages, meta = prompt_messages(endpoint, {"text": input_text}, prompt_id)
        response = await call_ollama_func(messages, temperature=meta["temperature"], model=meta["model"])
        return {
            "mode": "cmms-assistant",
            "response": response,
            "model": meta["model"],
            "prompt": meta,
            "safety": {"advisory_only": True, "cmms_write_back": False, "work_order_created": False, "email_sent": False},
        }
    if endpoint == "extract-work-order-fields":
        if request_factory is None:
            raise HTTPException(status_code=500, detail="Missing request factory")
        payload = request_factory(text=input_text, environment_code=environment_code, source=source)
        valid_buildings, valid_priorities, _env_code = resolve_validation_lists(payload)
        messages, meta = prompt_messages(
            endpoint,
            {
                "text": input_text,
                "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
                "valid_buildings": valid_buildings,
                "valid_priorities": valid_priorities,
            },
            prompt_id,
        )
        content = await call_ollama_func(messages, temperature=meta["temperature"], model=meta["model"])
        result = validate_extracted_fields(parse_json_response(content), valid_buildings, valid_priorities)
        result["prompt"] = meta
        return result
    if endpoint != "cmms-intake":
        raise HTTPException(status_code=400, detail="Unsupported test case endpoint")

    if request_factory is None:
        raise HTTPException(status_code=500, detail="Missing request factory")
    payload = request_factory(text=input_text, environment_code=environment_code, source=source)
    return await cmms_intake(
        payload,
        source=source,
        prompt_id=prompt_id,
        reviewer_prompt_id=reviewer_prompt_id,
        call_ollama_func=call_ollama_func,
    )


async def cmms_intake(
    payload: Any,
    *,
    user_id: int | None = None,
    api_key_id: str | None = None,
    source: str | None = None,
    prompt_id: int | None = None,
    reviewer_prompt_id: int | None = None,
    call_ollama_func: OllamaCaller = call_ollama,
) -> dict[str, Any]:
    env_hint = payload.environment_code.upper() if payload.environment_code else None
    intake_source = source if source is not None else payload.source
    workflow_mode = workflow_mode_for_payload(payload)
    run_id = start_workflow_run(
        "cmms-intake",
        environment_code=env_hint,
        user_id=user_id,
        api_key_id=api_key_id,
        source=intake_source,
    )
    current_step: int | None = None
    try:
        current_step = start_workflow_step(
            run_id,
            "request_received",
            10,
            input_summary=f"{redacted_summary(payload.text)} | source={intake_source or 'text'} environment={env_hint or 'none'}",
        )
        finish_workflow_step(current_step, "passed", output_summary="Request accepted for controlled intake workflow")
        current_step = None

        valid_buildings, valid_priorities, env_code = resolve_validation_lists(payload)

        current_step = start_workflow_step(
            run_id,
            "model_extraction",
            20,
            model=extractor_model_name(),
            prompt_version="pending",
            input_summary=f"text_length={len(payload.text)} buildings={len(valid_buildings)} priorities={len(valid_priorities)} mode={workflow_mode}",
        )
        prompt_context = {
            "text": payload.text,
            "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
            "valid_buildings": valid_buildings,
            "valid_priorities": valid_priorities,
        }
        intake_messages: dict[str, list[dict[str, str]]] | None = None
        fast_cache = {"enabled": False, "status": "disabled"}
        model_call_count = 2
        if workflow_mode == "fast":
            extraction_messages, prompt_meta = prompt_messages("extract-work-order-fields", prompt_context)
            prompt_meta = {**prompt_meta, "model": extractor_model_name()}
            db_execute(
                "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
                (prompt_meta["model"], f"{prompt_meta['prompt_id']}:{prompt_meta['prompt_version']}", current_step),
            )
            cache_key, _canonical_text = fast_extraction_cache_key(
                text=payload.text,
                environment_code=env_code,
                prompt_meta=prompt_meta,
                valid_buildings=valid_buildings,
                valid_priorities=valid_priorities,
            )
            cached_data = read_fast_extraction_cache(cache_key)
            if cached_data is not None:
                extracted_data = cached_data
                model_call_count = 0
                fast_cache = fast_cache_block("hit", cache_key)
            else:
                extracted_data = parse_json_response(
                    await call_ollama_func(extraction_messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
                )
                write_fast_extraction_cache(cache_key, extracted_data)
                model_call_count = 1
                fast_cache = fast_cache_block("miss", cache_key)
            request_type, confidence, fields, validation, extraction_context = validate_intake(
                extracted_data.get("request_type"),
                extracted_data.get("confidence"),
                extracted_data,
                valid_buildings,
                valid_priorities,
            )
        else:
            intake_messages, prompt_meta = intake_prompt_messages(prompt_context, prompt_id)
            db_execute(
                "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
                (prompt_meta["model"], f"{prompt_meta['prompt_id']}:{prompt_meta['prompt_version']}", current_step),
            )
            classifier_data = parse_json_response(await call_ollama_func(intake_messages["classifier"], temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
            extractor_data = parse_json_response(
                await call_ollama_func(
                    intake_messages["field_extractor"],
                    temperature=prompt_meta["temperature"],
                    model=extractor_model_name(),
                )
            )
            request_type, confidence, fields, validation, extraction_context = validate_intake(
                classifier_data.get("request_type"),
                classifier_data.get("confidence"),
                extractor_data,
                valid_buildings,
                valid_priorities,
            )
        metadata = build_intake_metadata(
            source=intake_source or "text",
            fields=fields,
            extracted=extract_metadata_from_text(payload.text),
        )
        if metadata["request"]["location_conflict"]:
            validation["needs_human_review"] = True
            warning = "Submitted location conflicts with extracted location."
            if warning not in validation["warnings"]:
                validation["warnings"].append(warning)

        finish_workflow_step(
            current_step,
            "passed",
            output_summary=f"type={request_type} confidence={confidence:.2f} missing={len(validation['missing_fields'])}",
            output_json={
                "request_type": request_type,
                "confidence": confidence,
                "model_call_count": model_call_count,
                "prompt_id": prompt_meta["prompt_id"],
                "prompt_version": prompt_meta["prompt_version"],
                "temperature": prompt_meta["temperature"],
                "cache": fast_cache,
                "fields": fields,
                "missing_fields": validation["missing_fields"],
                "invalid_code_candidates": extraction_context["invalid_code_candidates"],
            },
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "asset_resolution",
            25,
            input_summary=f"environment={env_code or 'none'} text_length={len(payload.text)}",
        )
        asset_context = resolve_asset_context(payload.text, env_code)
        asset_status = asset_context.get("status")
        asset_step_status = "passed" if asset_status == "resolved" else ("skipped" if asset_status == "skipped" else "warning")
        finish_workflow_step(
            current_step,
            asset_step_status,
            output_summary=f"asset_status={asset_status} candidates={len(asset_context.get('candidates') or [])}",
            output_json=asset_context,
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "work_order_planning",
            27,
            input_summary=f"asset_status={asset_status}",
        )
        work_order_plan = build_work_order_plan(asset_context)
        planning_status = "passed" if work_order_plan.get("status") == "planned" else "warning"
        finish_workflow_step(
            current_step,
            planning_status,
            output_summary=(
                f"plan_status={work_order_plan.get('status')} "
                f"likely_parts={len(work_order_plan.get('likely_parts') or [])}"
            ),
            output_json=work_order_plan,
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "inventory_check",
            27,
            input_summary=f"environment={env_code or 'none'} likely_parts={len(work_order_plan.get('likely_parts') or [])}",
        )
        inventory_context = resolve_inventory_context(work_order_plan, env_code)
        inventory_status = inventory_context.get("status")
        inventory_step_status = "passed" if inventory_status in {"available", "shortage", "not_required"} else ("skipped" if inventory_status == "skipped" else "warning")
        finish_workflow_step(
            current_step,
            inventory_step_status,
            output_summary=(
                f"inventory_status={inventory_status} "
                f"requires_procurement={bool(inventory_context.get('requires_procurement'))}"
            ),
            output_json=inventory_context,
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "procurement_planning",
            27,
            input_summary=f"inventory_status={inventory_status}",
        )
        procurement_request = build_procurement_request(run_id, env_code, work_order_plan, inventory_context)
        procurement_status = procurement_request.get("status")
        procurement_step_status = "passed" if procurement_status in {"drafted", "not_required"} else "warning"
        finish_workflow_step(
            current_step,
            procurement_step_status,
            output_summary=(
                f"procurement_status={procurement_status} "
                f"lines={len(procurement_request.get('lines') or [])}"
            ),
            output_json=procurement_request,
        )
        current_step = None

        assignment_trade = work_order_plan.get("trade") or request_type
        current_step = start_workflow_step(
            run_id,
            "assignment_resolution",
            28,
            input_summary=f"environment={env_code or 'none'} trade={assignment_trade or 'none'}",
        )
        assignment_context = resolve_assignment_context(payload.text, env_code, trade=assignment_trade)
        assignment_status = assignment_context.get("status")
        assignment_step_status = "passed" if assignment_status == "resolved" else ("skipped" if assignment_status == "skipped" else "warning")
        finish_workflow_step(
            current_step,
            assignment_step_status,
            output_summary=f"assignment_status={assignment_status} candidates={len(assignment_context.get('candidates') or [])}",
            output_json=assignment_context,
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "action_plan_composed",
            29,
            input_summary=f"assignment_status={assignment_status} procurement_status={procurement_status}",
        )
        action_plan = build_initial_action_plan(run_id, env_code, assignment_context, procurement_request)
        finish_workflow_step(
            current_step,
            "passed",
            output_summary=f"actions={len(action_plan.get('actions') or [])}",
            output_json=action_plan,
        )
        current_step = None
        orchestration_summary = build_orchestration_summary(
            run_id=run_id,
            environment_code=env_code,
            priority=fields["priority"],
            work_order_type=request_type,
            asset_context=asset_context,
            assignment_context=assignment_context,
            inventory_context=inventory_context,
            procurement_request=procurement_request,
            action_plan=action_plan,
        )

        location = metadata["request"]["location"]
        metadata_review = unreviewed_metadata_review()
        save_extracted_metadata_review(run_id, metadata["submission"], metadata["request"])
        result_payload = {
            "summary": fields["summary"],
            "building": location.get("building") or fields["building"],
            "room": location.get("room") or fields["room"],
            "priority": fields["priority"],
            "work_order_type": request_type,
            "assign_to": None,
            "issue_to": None,
            "job_type": None,
            "confidence": confidence,
            "submission": metadata["submission"],
            "request": metadata["request"],
            "metadata_review": metadata_review,
            "asset_context": asset_context,
            "work_order_plan": work_order_plan,
            "assignment_context": assignment_context,
            "inventory_context": inventory_context,
            "procurement_request": procurement_request,
            "orchestration_summary": orchestration_summary,
            "action_plan": action_plan,
        }
        result_payload = apply_assignment_to_payload(result_payload, assignment_context)

        current_step = start_workflow_step(run_id, "output_contract_validation", 30, input_summary="endpoint=cmms-intake")
        contract_validation = validate_output_contract("cmms-intake", result_payload)
        contract_status = "passed" if contract_validation["valid"] else "failed"
        finish_workflow_step(
            current_step,
            contract_status,
            output_summary=f"contract_valid={contract_validation['valid']} errors={len(contract_validation['errors'])}",
            output_json={
                "contract_version": contract_validation["contract_version"],
                "valid": contract_validation["valid"],
                "error_count": len(contract_validation["errors"]),
                "warning_count": len(contract_validation["warnings"]),
            },
        )
        current_step = None
        contract_block = {
            "version": contract_validation["contract_version"],
            "valid": contract_validation["valid"],
            "errors": contract_validation["errors"],
            "warnings": contract_validation["warnings"],
        }

        current_step = start_workflow_step(
            run_id,
            "code_normalization_suggestion_agent",
            35,
            input_summary=f"contract_valid={contract_validation['valid']} environment={env_code or 'none'}",
        )
        code_values: dict[str, list[dict[str, Any]]] = {}
        if env_code and contract_validation["valid"]:
            code_values = load_code_values_for_normalizer(env_code)
            extraction_context["invalid_code_candidates"] = collect_invalid_code_candidates(
                result=contract_validation["normalized_payload"],
                existing_candidates=extraction_context["invalid_code_candidates"],
                code_values=code_values,
            )
        should_run_normalizer = (
            env_code
            and contract_validation["valid"]
            and (workflow_mode == "full" or bool(extraction_context.get("invalid_code_candidates")))
        )
        if should_run_normalizer:
            try:
                normalizer_context = build_code_normalizer_context(
                    text=payload.text,
                    text_summary=redacted_summary(payload.text, max_len=500),
                    environment_code=env_code,
                    result=contract_validation["normalized_payload"],
                    raw_extracted_fields=extraction_context["raw_extracted_fields"],
                    invalid_code_candidates=extraction_context["invalid_code_candidates"],
                    code_values=code_values,
                )
                normalizer_messages, normalizer_prompt_meta = prompt_messages(
                    "cmms-code-normalizer",
                    {"context_json": normalizer_context},
                )
                db_execute(
                    "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
                    (
                        normalizer_prompt_meta["model"],
                        f"{normalizer_prompt_meta['prompt_id']}:{normalizer_prompt_meta['prompt_version']}",
                        current_step,
                    ),
                )
                normalizer_raw = await call_ollama_func(
                    normalizer_messages,
                    temperature=normalizer_prompt_meta["temperature"],
                    model=normalizer_prompt_meta["model"],
                )
                normalizer_data = parse_json_response(normalizer_raw)
                normalized_suggestions = normalize_code_normalizer_output(
                    normalizer_data,
                    enabled_codes_by_field=enabled_codes_by_field(code_values),
                )
                code_normalization = apply_code_normalization_suggestions(
                    result=contract_validation["normalized_payload"],
                    invalid_code_candidates=extraction_context["invalid_code_candidates"],
                    normalized_model_output=normalized_suggestions,
                )
                if code_normalization["applied"]:
                    contract_validation["normalized_payload"] = contract_validation["normalized_payload"] | code_normalization["applied"]
                    fields = fields | {key: value for key, value in code_normalization["applied"].items() if key in fields}
                normalizer_step_status = "warning" if code_normalization["rejected"] and not code_normalization["applied"] else "passed"
                finish_workflow_step(
                    current_step,
                    normalizer_step_status,
                    output_summary=(
                        f"status={code_normalization['status']} "
                        f"suggestions={len(code_normalization['suggestions'])} "
                        f"rejected={len(code_normalization['rejected'])}"
                    ),
                    output_json={
                        "status": code_normalization["status"],
                        "suggestion_count": len(code_normalization["suggestions"]),
                        "accepted_count": len(code_normalization["applied"]),
                        "rejected_count": len(code_normalization["rejected"]),
                        "rejected_reasons": sorted(
                            {
                                item.get("reason_code", "unknown")
                                for item in code_normalization["rejected"]
                                if isinstance(item, dict)
                            }
                        ),
                        "prompt_id": normalizer_prompt_meta["prompt_id"],
                        "prompt_version": normalizer_prompt_meta["prompt_version"],
                    },
                )
            except Exception as exc:
                code_normalization = failed_code_normalization_block("Code normalization failed.")
                finish_workflow_step(
                    current_step,
                    "failed",
                    output_summary="Code normalization failed.",
                    output_json={"status": "failed", "message": str(exc)[:200]},
                )
        else:
            if workflow_mode == "fast" and not extraction_context.get("invalid_code_candidates"):
                message = "Skipped in fast mode because extracted codes are already valid."
            else:
                message = "Skipped because output contract validation failed." if env_code else "Skipped because no environment_code was supplied."
            code_normalization = skipped_code_normalization_block(message)
            finish_workflow_step(
                current_step,
                "skipped",
                output_summary=message,
                output_json={"status": code_normalization["status"], "enabled": code_normalization["enabled"]},
            )
        current_step = None

        current_step = start_workflow_step(run_id, "environment_validation", 40, input_summary=f"environment={env_code or 'none'}")
        if env_code and contract_validation["valid"]:
            ai_validation = validate_ai_output(
                env_code,
                contract_validation["normalized_payload"],
            )
            ai_validation["enabled"] = True
            ai_validation["status"] = "completed"
            env_status = "failed" if ai_validation["valid"] is False else ("warning" if ai_validation.get("warnings") else "passed")
            finish_workflow_step(
                current_step,
                env_status,
                output_summary=f"validation_valid={ai_validation['valid']} warnings={len(ai_validation.get('warnings', []))} errors={len(ai_validation.get('errors', []))}",
                output_json={
                    "valid": ai_validation["valid"],
                    "error_count": len(ai_validation.get("errors", [])),
                    "warning_count": len(ai_validation.get("warnings", [])),
                    "normalized": ai_validation.get("normalized", {}),
                },
            )
            current_step = None
        else:
            ai_validation = skipped_ai_validation() if env_code else {
                "enabled": False,
                "valid": None,
                "status": "not_run",
                "message": "No environment_code was supplied.",
                "errors": [],
                "warnings": [],
                "normalized": {},
            }
            finish_workflow_step(
                current_step,
                "skipped",
                output_summary="Skipped because output contract validation failed." if env_code else "Skipped because no environment_code was supplied.",
                output_json={"status": ai_validation.get("status"), "valid": ai_validation.get("valid")},
            )
            current_step = None

        current_step = start_workflow_step(
            run_id,
            "draft_generation",
            43,
            model=None if workflow_mode == "fast" else prompt_meta["model"],
            prompt_version=None if workflow_mode == "fast" else f"{prompt_meta['prompt_id']}:{prompt_meta['prompt_version']}",
            input_summary=f"validation_valid={ai_validation.get('valid')}",
        )
        if workflow_mode == "fast":
            drafts = deterministic_fast_drafts(
                fields=fields,
                result_payload=contract_validation["normalized_payload"] if contract_validation["valid"] else result_payload,
                assignment_context=assignment_context,
                inventory_context=inventory_context,
                procurement_request=procurement_request,
            )
            draft_summary = "Deterministic fast draft generated."
        else:
            draft_context = {
                "text": payload.text,
                "request_type": request_type,
                "fields": fields,
                "validation": validation,
                "contract": contract_block,
                "ai_validation": ai_validation,
                "code_normalization": code_normalization,
                "asset_context": asset_context,
                "work_order_plan": work_order_plan,
                "assignment_context": assignment_context,
                "inventory_context": inventory_context,
                "procurement_request": procurement_request,
                "orchestration_summary": orchestration_summary,
                "action_plan": action_plan,
                "submission": metadata["submission"],
                "request": metadata["request"],
            }
            draft_messages = [
                (intake_messages or {})["draft_generator"][0],
                {"role": "user", "content": json.dumps(draft_context)},
            ]
            draft_data = parse_json_response(
                await call_ollama_func(draft_messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
            )
            drafts = {
                "draft_wo_description": str(draft_data.get("draft_wo_description") or fields["summary"]),
                "internal_note": str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."),
                "client_reply": str(draft_data.get("client_reply") or "Thanks, we captured your request."),
            }
            draft_summary = "Draft text generated after validation."
        finish_workflow_step(
            current_step,
            "passed",
            output_summary=draft_summary,
            output_json={"draft_fields": sorted(drafts.keys())},
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "safety_reviewer_agent",
            45,
            input_summary=f"contract_valid={contract_validation['valid']}",
        )
        if workflow_mode == "fast":
            review = fast_mode_reviewer_block()
            finish_workflow_step(
                current_step,
                "skipped",
                output_summary=review["message"],
                output_json={"status": review["status"], "enabled": review["enabled"], "source": review["source"]},
            )
        elif contract_validation["valid"]:
            review, reviewer_prompt_meta = await run_safety_reviewer_agent(
                result=contract_validation["normalized_payload"],
                contract=contract_block,
                ai_validation=ai_validation,
                drafts=drafts,
                call_ollama_func=call_ollama_func,
                prompt_id=reviewer_prompt_id,
            )
            db_execute(
                "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
                (
                    reviewer_prompt_meta["model"],
                    f"{reviewer_prompt_meta['prompt_id']}:{reviewer_prompt_meta['prompt_version']}",
                    current_step,
                ),
            )
            reviewer_status = "failed" if review["status"] == "fail" else ("warning" if review["status"] == "warning" else "passed")
            finish_workflow_step(
                current_step,
                reviewer_status,
                output_summary=f"review_status={review['status']} flags={len(review['risk_flags'])} notes={len(review['notes'])}",
                output_json={
                    "status": review["status"],
                    "human_review_recommended": review["human_review_recommended"],
                    "risk_flag_count": len(review["risk_flags"]),
                    "note_count": len(review["notes"]),
                    "prompt_id": reviewer_prompt_meta["prompt_id"],
                    "prompt_version": reviewer_prompt_meta["prompt_version"],
                },
            )
        else:
            review = skipped_reviewer_block("Skipped because output contract validation failed.")
            finish_workflow_step(
                current_step,
                "skipped",
                output_summary=review["message"],
                output_json={"status": review["status"], "enabled": review["enabled"]},
            )
        current_step = None

        current_step = start_workflow_step(run_id, "cmms_auto_push", 48, input_summary=f"environment={env_code or 'none'}")
        cmms_push = build_cmms_intake_push_result(
            run_id=run_id,
            environment_code=env_code,
            payload=contract_validation["normalized_payload"] if contract_validation["valid"] else result_payload,
            contract_valid=contract_validation["valid"],
            ai_validation=ai_validation,
            validation=validation,
            review=review,
            metadata_review=metadata_review,
            workflow_mode=workflow_mode,
        )
        action_plan = finalize_action_plan(action_plan, cmms_push)
        orchestration_summary = build_orchestration_summary(
            run_id=run_id,
            environment_code=env_code,
            priority=fields["priority"],
            work_order_type=request_type,
            asset_context=asset_context,
            assignment_context=assignment_context,
            inventory_context=inventory_context,
            procurement_request=procurement_request,
            action_plan=action_plan,
            cmms_push=cmms_push,
        )
        response_result = contract_validation["normalized_payload"] if contract_validation["valid"] else result_payload
        response_result = response_result | {"action_plan": action_plan, "orchestration_summary": orchestration_summary}
        push_step_status = "passed" if cmms_push["status"] in {"sent", "skipped"} else ("warning" if cmms_push["status"] == "blocked" else "failed")
        finish_workflow_step(
            current_step,
            push_step_status,
            output_summary=f"cmms_push={cmms_push['status']}",
            output_json=cmms_push,
        )
        current_step = None

        current_step = start_workflow_step(
            run_id,
            "orchestration_summary",
            49,
            input_summary=f"status={orchestration_summary['status']} actions={len(orchestration_summary['requested_actions'])}",
        )
        finish_workflow_step(
            current_step,
            "warning" if orchestration_summary["status"] in {"needs_review", "blocked"} else "passed",
            output_summary=orchestration_summary["operator_message"],
            output_json=orchestration_summary,
        )
        current_step = None

        current_step = start_workflow_step(run_id, "response_composed", 50)
        run_status = "failed" if not contract_validation["valid"] else ("completed_with_warnings" if ai_validation.get("warnings") else "completed")
        finish_workflow_step(current_step, "passed", output_summary=f"run_status={run_status}")
        current_step = None
        finish_workflow_run(run_id, run_status)
        return {
            "run_id": run_id,
            "endpoint": "cmms-intake",
            "workflow_mode": workflow_mode,
            "fast_cache": fast_cache,
            "environment_code": env_code,
            "trace": {"available": True, "run_id": run_id},
            "contract": contract_block,
            "result": response_result,
            "ai_validation": ai_validation,
            "code_normalization": code_normalization,
            "asset_context": asset_context,
            "work_order_plan": work_order_plan,
            "assignment_context": assignment_context,
            "inventory_context": inventory_context,
            "procurement_request": procurement_request,
            "orchestration_summary": orchestration_summary,
            "action_plan": action_plan,
            "review": review,
            "cmms_push": cmms_push,
            "submission": metadata["submission"],
            "request": metadata["request"],
            "metadata_review": metadata_review,
            "raw": {"included": False},
            "request_type": request_type,
            "classification_confidence": confidence,
            "fields": fields,
            "validation": validation,
            "drafts": drafts,
            "model": prompt_meta["model"],
        }
    except Exception as exc:
        if current_step is not None:
            fail_workflow_step(current_step, str(exc))
        finish_workflow_run(run_id, "failed", str(exc))
        raise
