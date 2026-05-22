"""Controlled CMMS AI endpoint orchestration and Ollama call helpers."""

import json
from typing import Any, Awaitable, Callable

import httpx
from fastapi import HTTPException

from .config import ADVISORY_WARNING, ALLOWED_REQUEST_TYPES, MODEL_NAME, OLLAMA_CHAT_URL
from .db import db_execute
from .environments import get_environment_values
from .intake_metadata import build_intake_metadata, extract_metadata_from_text, unreviewed_metadata_review
from .intake_metadata_reviews import save_extracted_metadata_review
from .output_contracts import skipped_ai_validation, validate_output_contract
from .prompts import intake_prompt_messages, prompt_messages
from .validation_rules import validate_ai_output
from .workflow_trace import (
    fail_workflow_step,
    finish_workflow_run,
    finish_workflow_step,
    start_workflow_run,
    start_workflow_step,
)

OllamaCaller = Callable[..., Awaitable[str]]


def normalize_allowed_values(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


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

    request_type = data.get("request_type")
    if request_type not in ALLOWED_REQUEST_TYPES:
        request_type = "Unknown"

    building = data.get("building")
    building = building.strip() if isinstance(building, str) else None
    building = building or None

    room = data.get("room")
    room = room.strip() if isinstance(room, str) else None
    room = room or None

    priority = data.get("priority")
    priority = priority.strip() if isinstance(priority, str) else None
    if priority not in allowed_priorities:
        priority = "NORMAL"

    summary = data.get("summary")
    summary = summary.strip() if isinstance(summary, str) and summary.strip() else ""

    missing_fields = normalize_missing_fields(data.get("missing_fields"))
    if not building or building not in allowed_buildings:
        building = None
        ensure_missing_field(missing_fields, "building")
    if not room:
        ensure_missing_field(missing_fields, "room")

    needs_human_review = bool(data.get("needs_human_review"))
    if not building or not room:
        needs_human_review = True

    return {
        "request_type": request_type,
        "building": building,
        "room": room,
        "priority": priority or "NORMAL",
        "summary": summary,
        "missing_fields": normalize_missing_fields(missing_fields),
        "needs_human_review": needs_human_review,
        "confidence": clamp_confidence(data.get("confidence")),
    }


def validate_intake(
    request_type: str,
    confidence: Any,
    field_data: dict[str, Any],
    valid_buildings: list[str],
    valid_priorities: list[str],
) -> tuple[str, float, dict[str, Any], dict[str, Any]]:
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
    return validated["request_type"], validated["confidence"], fields, validation


def redacted_summary(text: str, max_len: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned


async def summarize_work_order(payload: Any, call_ollama_func: OllamaCaller = call_ollama) -> dict[str, Any]:
    messages, prompt_meta = prompt_messages("summarize-work-order", {"text": payload.text})
    summary = await call_ollama_func(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
    return {"summary": summary}


async def cmms_assistant(payload: Any, call_ollama_func: OllamaCaller = call_ollama) -> dict[str, Any]:
    messages, prompt_meta = prompt_messages("cmms-assistant", {"text": payload.text})
    content = await call_ollama_func(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
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
    content = await call_ollama_func(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
    data = parse_json_response(content)
    result = validate_extracted_fields(data, valid_buildings, valid_priorities)
    return result | {"_environment_code": env_code}


async def execute_ai_endpoint_for_test(
    endpoint: str,
    input_text: str,
    environment_code: str | None,
    source: str = "test_case",
    prompt_id: int | None = None,
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
    return await cmms_intake(payload, source=source, prompt_id=prompt_id, call_ollama_func=call_ollama_func)


async def cmms_intake(
    payload: Any,
    *,
    user_id: int | None = None,
    api_key_id: str | None = None,
    source: str | None = None,
    prompt_id: int | None = None,
    call_ollama_func: OllamaCaller = call_ollama,
) -> dict[str, Any]:
    env_hint = payload.environment_code.upper() if payload.environment_code else None
    intake_source = source if source is not None else payload.source
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
            model=MODEL_NAME,
            prompt_version="pending",
            input_summary=f"text_length={len(payload.text)} buildings={len(valid_buildings)} priorities={len(valid_priorities)}",
        )
        intake_messages, prompt_meta = intake_prompt_messages(
            {
                "text": payload.text,
                "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
                "valid_buildings": valid_buildings,
                "valid_priorities": valid_priorities,
            },
            prompt_id,
        )
        db_execute(
            "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
            (prompt_meta["model"], f"{prompt_meta['prompt_id']}:{prompt_meta['prompt_version']}", current_step),
        )
        classifier_data = parse_json_response(await call_ollama_func(intake_messages["classifier"], temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
        extractor_data = parse_json_response(await call_ollama_func(intake_messages["field_extractor"], temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
        request_type, confidence, fields, validation = validate_intake(
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
        draft_context = {
            "text": payload.text,
            "request_type": request_type,
            "fields": fields,
            "validation": validation,
            "submission": metadata["submission"],
            "request": metadata["request"],
        }
        draft_messages = [
            intake_messages["draft_generator"][0],
            {"role": "user", "content": json.dumps(draft_context)},
        ]
        draft_data = parse_json_response(await call_ollama_func(draft_messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
        finish_workflow_step(
            current_step,
            "passed",
            output_summary=f"type={request_type} confidence={confidence:.2f} missing={len(validation['missing_fields'])}",
            output_json={
                "request_type": request_type,
                "confidence": confidence,
                "model_call_count": 3,
                "prompt_id": prompt_meta["prompt_id"],
                "prompt_version": prompt_meta["prompt_version"],
                "temperature": prompt_meta["temperature"],
                "fields": fields,
                "missing_fields": validation["missing_fields"],
            },
        )
        current_step = None

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
        }

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

        current_step = start_workflow_step(run_id, "response_composed", 50)
        drafts = {
            "draft_wo_description": str(draft_data.get("draft_wo_description") or fields["summary"]),
            "internal_note": str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."),
            "client_reply": str(draft_data.get("client_reply") or "Thanks, we captured your request."),
        }
        run_status = "failed" if not contract_validation["valid"] else ("completed_with_warnings" if ai_validation.get("warnings") else "completed")
        finish_workflow_step(current_step, "passed", output_summary=f"run_status={run_status}")
        current_step = None
        finish_workflow_run(run_id, run_status)
        return {
            "run_id": run_id,
            "endpoint": "cmms-intake",
            "environment_code": env_code,
            "trace": {"available": True, "run_id": run_id},
            "contract": contract_block,
            "result": contract_validation["normalized_payload"] if contract_validation["valid"] else result_payload,
            "ai_validation": ai_validation,
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
