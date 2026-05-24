"""Deterministic CMMS action-plan helpers."""

from __future__ import annotations

from typing import Any


def create_work_order_idempotency_key(run_id: Any) -> str:
    return f"cmms-run-{run_id}-create-work-order"


def assign_work_order_idempotency_key(run_id: Any) -> str:
    return f"cmms-run-{run_id}-assign-work-order"


def purchase_request_idempotency_key(run_id: Any) -> str:
    return f"cmms-run-{run_id}-create-purchase-request"


def assignment_action_status(assignment_context: dict[str, Any]) -> str:
    if assignment_context.get("status") == "resolved":
        return "ready"
    if assignment_context.get("status") == "skipped":
        return "skipped"
    return "needs_review"


def build_initial_action_plan(
    run_id: Any,
    environment_code: str | None,
    assignment_context: dict[str, Any],
    procurement_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assignment = assignment_context.get("assignment") if isinstance(assignment_context.get("assignment"), dict) else {}
    assignment_status = assignment_action_status(assignment_context)
    actions = [
        {
            "action_id": "create_work_order",
            "type": "cmms.work_order.create",
            "status": "planned",
            "requires_review": False,
            "idempotency_key": create_work_order_idempotency_key(run_id),
            "reasons": [],
        },
        {
            "action_id": "assign_work_order",
            "type": "cmms.work_order.assign",
            "status": assignment_status,
            "requires_review": assignment_status == "needs_review",
            "idempotency_key": assign_work_order_idempotency_key(run_id),
            "method": "included_in_create_payload",
            "technician": assignment_context.get("technician"),
            "assignment": {
                "assign_to": assignment.get("assign_to"),
                "issue_to": assignment.get("issue_to"),
                "job_type": assignment.get("job_type"),
            },
            "reasons": list(assignment_context.get("reasons") or []),
        },
    ]
    if procurement_request and procurement_request.get("status") == "drafted":
        actions.append(
            {
                "action_id": "create_purchase_request",
                "type": "procurement.purchase_request.create",
                "status": "dry_run",
                "requires_review": False,
                "idempotency_key": purchase_request_idempotency_key(run_id),
                "method": "local_fake_connector",
                "request": procurement_request,
                "reasons": [procurement_request.get("reason")],
            }
        )
    elif procurement_request and procurement_request.get("status") == "needs_review":
        actions.append(
            {
                "action_id": "create_purchase_request",
                "type": "procurement.purchase_request.create",
                "status": "needs_review",
                "requires_review": True,
                "idempotency_key": purchase_request_idempotency_key(run_id),
                "method": "local_fake_connector",
                "request": procurement_request,
                "reasons": [procurement_request.get("reason")],
            }
        )
    return {
        "schema": "cmms_action_plan_v1",
        "run_id": run_id,
        "environment_code": str(environment_code).upper() if environment_code else None,
        "actions": actions,
    }


def push_status_to_action_status(cmms_push: dict[str, Any]) -> str:
    status = cmms_push.get("status")
    if status == "sent":
        return "succeeded"
    if status == "dry_run":
        return "dry_run"
    if status == "blocked":
        return "blocked"
    if status == "skipped":
        return "skipped"
    if status == "failed":
        return "failed"
    return "planned"


def finalize_action_plan(action_plan: dict[str, Any], cmms_push: dict[str, Any]) -> dict[str, Any]:
    finalized = {
        **action_plan,
        "actions": [dict(action) for action in action_plan.get("actions", []) if isinstance(action, dict)],
    }
    if not finalized["actions"]:
        return finalized

    create_action = finalized["actions"][0]
    create_status = push_status_to_action_status(cmms_push)
    create_action["status"] = create_status
    create_action["external_reference"] = cmms_push.get("external_reference")
    create_action["blocked_reasons"] = list(cmms_push.get("blocked_reasons") or [])

    if len(finalized["actions"]) < 2:
        return finalized

    assign_action = finalized["actions"][1]
    if assign_action.get("status") == "ready":
        if create_status in {"succeeded", "dry_run"}:
            assign_action["status"] = create_status
            assign_action["external_reference"] = cmms_push.get("external_reference")
        else:
            assign_action["status"] = "blocked"
            reasons = list(assign_action.get("reasons") or [])
            if "create_work_order_not_succeeded" not in reasons:
                reasons.append("create_work_order_not_succeeded")
            assign_action["reasons"] = reasons
    return finalized
