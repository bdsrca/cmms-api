"""CMMS handoff candidates built from reviewed intake workflow data."""

from typing import Any


def model_extraction_output(run: dict[str, Any]) -> dict[str, Any]:
    for step in run.get("steps") or []:
        if step.get("step_name") == "model_extraction" and isinstance(step.get("output_json"), dict):
            return step["output_json"]
    return {}


def issue_messages(issues: Any) -> list[str]:
    messages: list[str] = []
    for issue in issues if isinstance(issues, list) else []:
        if isinstance(issue, dict):
            message = str(issue.get("message") or "").strip()
        else:
            message = str(issue).strip()
        if message:
            messages.append(message)
    return messages


def derive_environment_preview_status(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "blocked"
    if warnings:
        return "needs_review"
    return "ready"


def build_canonical_cmms_payload_preview(payload: dict[str, Any], run_id: Any) -> dict[str, Any]:
    return {
        "schema": "canonical_cmms_work_order_v1",
        "fields": {
            "summary": payload.get("summary"),
            "location": {
                "building": payload.get("building"),
                "room": payload.get("room"),
            },
            "priority": payload.get("priority"),
            "work_order_type": payload.get("work_order_type"),
            "assignment": {
                "assign_to": payload.get("assign_to"),
                "issue_to": payload.get("issue_to"),
                "job_type": payload.get("job_type"),
            },
            "requester": {
                "name": payload.get("submitted_by"),
                "email": payload.get("submitted_email"),
                "phone": payload.get("submitted_phone"),
            },
            "requested_due_date": payload.get("requested_due"),
            "source": {
                "method": payload.get("submitted_method"),
                "submitted_at": payload.get("submitted_at"),
                "intake_run_id": run_id,
            },
        },
    }


def environment_handoff_fields(canonical_preview: dict[str, Any]) -> dict[str, Any]:
    fields = canonical_preview.get("fields") if isinstance(canonical_preview.get("fields"), dict) else {}
    location = fields.get("location") if isinstance(fields.get("location"), dict) else {}
    assignment = fields.get("assignment") if isinstance(fields.get("assignment"), dict) else {}
    requester = fields.get("requester") if isinstance(fields.get("requester"), dict) else {}
    source = fields.get("source") if isinstance(fields.get("source"), dict) else {}
    return {
        "summary": fields.get("summary"),
        "building": location.get("building"),
        "room": location.get("room"),
        "priority": fields.get("priority"),
        "work_order_type": fields.get("work_order_type"),
        "assign_to": assignment.get("assign_to"),
        "issue_to": assignment.get("issue_to"),
        "job_type": assignment.get("job_type"),
        "requester_name": requester.get("name"),
        "requester_email": requester.get("email"),
        "requester_phone": requester.get("phone"),
        "requested_due_date": fields.get("requested_due_date"),
        "source_method": source.get("method"),
        "intake_run_id": source.get("intake_run_id"),
    }


def handoff_assignment_warnings(fields: dict[str, Any]) -> list[str]:
    warnings = []
    labels = {
        "assign_to": "Assign To",
        "issue_to": "Issue To",
        "job_type": "Job Type",
    }
    for field, label in labels.items():
        if not str(fields.get(field) or "").strip():
            warnings.append(f"{label} is empty.")
    return warnings


def build_environment_handoff_preview(
    canonical_preview: dict[str, Any],
    environment_code: Any,
    *,
    get_environment_values_func: Any = None,
    validate_func: Any = None,
) -> dict[str, Any] | None:
    if not environment_code:
        return None

    env_code = str(environment_code).upper()
    fields = environment_handoff_fields(canonical_preview)
    base = {
        "schema": "environment_cmms_handoff_v1",
        "environment_code": env_code,
        "fields": fields,
    }
    if not isinstance(canonical_preview.get("fields"), dict):
        return {
            **base,
            "status": "blocked",
            "validation": {
                "valid": False,
                "missing_fields": [],
                "errors": ["Candidate lacks a usable canonical CMMS preview."],
                "warnings": [],
                "normalized": {},
            },
        }

    try:
        if get_environment_values_func is None or validate_func is None:
            from .environments import get_environment_values
            from .validation_rules import validate_ai_output

            get_environment_values_func = get_environment_values_func or get_environment_values
            validate_func = validate_func or validate_ai_output
        get_environment_values_func(env_code)
        validation = validate_func(env_code, fields)
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        message = str(detail or exc)
        return {
            **base,
            "status": "blocked",
            "validation": {
                "valid": False,
                "missing_fields": [],
                "errors": [message],
                "warnings": [],
                "normalized": {},
            },
        }

    validation = validation if isinstance(validation, dict) else {}
    errors = issue_messages(validation.get("errors"))
    warnings = issue_messages(validation.get("warnings")) + handoff_assignment_warnings(fields)
    missing_fields = [
        str(issue.get("field"))
        for issue in validation.get("errors", [])
        if isinstance(issue, dict) and not str(issue.get("value") or "").strip()
    ]
    status = derive_environment_preview_status(errors, warnings)
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    return {
        **base,
        "status": status,
        "validation": {
            "valid": status == "ready",
            "missing_fields": missing_fields,
            "errors": errors,
            "warnings": warnings,
            "normalized": normalized,
        },
    }


def build_cmms_handoff_candidate(run: dict[str, Any], review: dict[str, Any]) -> dict[str, Any] | None:
    extraction = model_extraction_output(run)
    fields = extraction.get("fields") if isinstance(extraction.get("fields"), dict) else {}
    if not fields or not extraction.get("request_type"):
        return None

    submission = review.get("submission") if isinstance(review.get("submission"), dict) else {}
    request = review.get("request") if isinstance(review.get("request"), dict) else {}
    location = request.get("location") if isinstance(request.get("location"), dict) else {}
    payload = {
        "summary": fields.get("summary"),
        "building": location.get("building") or fields.get("building"),
        "room": location.get("room") or fields.get("room"),
        "priority": fields.get("priority"),
        "work_order_type": extraction.get("request_type"),
        "assign_to": None,
        "issue_to": None,
        "job_type": None,
        "requested_due": request.get("requested_due"),
        "submitted_by": submission.get("submitted_by"),
        "submitted_email": submission.get("submitted_email"),
        "submitted_phone": submission.get("submitted_phone"),
        "submitted_at": submission.get("submitted_at"),
        "submitted_method": submission.get("submitted_method"),
    }
    cmms_payload_preview = build_canonical_cmms_payload_preview(payload, run.get("run_id"))
    environment_handoff_preview = build_environment_handoff_preview(cmms_payload_preview, run.get("environment_code"))
    return {
        "kind": "cmms_work_order_candidate",
        "run_id": run.get("run_id"),
        "environment_code": run.get("environment_code"),
        "source": run.get("source"),
        "safety": {
            "advisory_only": True,
            "cmms_write_back": False,
            "work_order_created": False,
        },
        "metadata_review": review.get("metadata_review") or {},
        "payload": payload,
        "cmms_payload_preview": cmms_payload_preview,
        "environment_handoff_preview": environment_handoff_preview,
    }
