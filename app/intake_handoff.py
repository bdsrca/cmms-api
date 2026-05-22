"""CMMS handoff candidates built from reviewed intake workflow data."""

from typing import Any


def model_extraction_output(run: dict[str, Any]) -> dict[str, Any]:
    for step in run.get("steps") or []:
        if step.get("step_name") == "model_extraction" and isinstance(step.get("output_json"), dict):
            return step["output_json"]
    return {}


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
        "cmms_payload_preview": build_canonical_cmms_payload_preview(payload, run.get("run_id")),
    }
