"""Operator-facing summary for deterministic CMMS orchestration."""

from __future__ import annotations

from typing import Any


def action_map(action_plan: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    actions = action_plan.get("actions") if isinstance(action_plan, dict) else []
    return {
        str(action.get("action_id")): action
        for action in actions
        if isinstance(action, dict) and action.get("action_id")
    }


def action_status(actions: dict[str, dict[str, Any]], action_id: str, default: str = "not_planned") -> str:
    return str((actions.get(action_id) or {}).get("status") or default)


def context_reasons(*contexts: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    for context in contexts:
        if not isinstance(context, dict):
            continue
        for reason in context.get("reasons") or []:
            text = str(reason or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    return reasons


def review_required(*contexts: dict[str, Any] | None, action_plan: dict[str, Any] | None = None) -> bool:
    if any(bool(context.get("requires_review")) for context in contexts if isinstance(context, dict)):
        return True
    actions = action_plan.get("actions") if isinstance(action_plan, dict) else []
    return any(bool(action.get("requires_review")) for action in actions if isinstance(action, dict))


def dry_run_actions(actions: dict[str, dict[str, Any]]) -> list[str]:
    return [action_id for action_id, action in actions.items() if action.get("status") == "dry_run"]


def blocked_reasons(actions: dict[str, dict[str, Any]], cmms_push: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    if isinstance(cmms_push, dict):
        for reason in cmms_push.get("blocked_reasons") or []:
            text = str(reason or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    for action in actions.values():
        if action.get("status") not in {"blocked", "failed", "needs_review"}:
            continue
        for reason in action.get("blocked_reasons") or action.get("reasons") or []:
            text = str(reason or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    return reasons


def overall_status(
    *,
    human_review_required: bool,
    actions: dict[str, dict[str, Any]],
    cmms_push: dict[str, Any] | None,
) -> str:
    if human_review_required:
        return "needs_review"
    statuses = {str(action.get("status") or "") for action in actions.values()}
    push_status = str((cmms_push or {}).get("status") or "")
    if "failed" in statuses or push_status == "failed":
        return "failed"
    if "blocked" in statuses or push_status == "blocked":
        return "blocked"
    if "dry_run" in statuses or push_status == "dry_run":
        return "dry_run"
    if statuses and statuses <= {"succeeded", "skipped"}:
        return "ready"
    return "planned"


def requested_actions(actions: dict[str, dict[str, Any]], inventory_context: dict[str, Any] | None, procurement_request: dict[str, Any] | None) -> list[str]:
    requested = []
    for action_id in ("create_work_order", "assign_work_order"):
        if action_id in actions:
            requested.append(action_id)
    if isinstance(inventory_context, dict) and inventory_context.get("status") not in {None, "skipped", "not_required"}:
        requested.append("check_inventory")
    if "create_purchase_request" in actions or (isinstance(procurement_request, dict) and procurement_request.get("status") == "drafted"):
        requested.append("create_purchase_request")
    return requested


def first_shortage_item(inventory_context: dict[str, Any] | None) -> dict[str, Any] | None:
    items = inventory_context.get("items") if isinstance(inventory_context, dict) else []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and item.get("status") == "shortage":
            return item
    return None


def operator_message(
    *,
    asset_code: str | None,
    technician: str | None,
    inventory_context: dict[str, Any] | None,
    procurement_request: dict[str, Any] | None,
    status: str,
) -> str:
    target = f" for {asset_code}" if asset_code else ""
    parts = [f"Work order orchestration{target} is {status}."]
    if technician:
        parts.append(f"Assignment targets {technician}.")
    shortage = first_shortage_item(inventory_context)
    if shortage:
        parts.append(
            f"Inventory shortage: {shortage.get('part_number')} has {shortage.get('quantity_on_hand')} on hand "
            f"and shortage of {shortage.get('shortage_quantity')}."
        )
    if isinstance(procurement_request, dict) and procurement_request.get("status") == "drafted":
        parts.append("A purchase request draft is included.")
    return " ".join(parts)


def build_orchestration_summary(
    *,
    run_id: Any,
    environment_code: str | None,
    priority: str | None,
    work_order_type: str | None,
    asset_context: dict[str, Any] | None,
    assignment_context: dict[str, Any] | None,
    inventory_context: dict[str, Any] | None,
    procurement_request: dict[str, Any] | None,
    action_plan: dict[str, Any] | None,
    cmms_push: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actions = action_map(action_plan)
    asset = asset_context.get("asset") if isinstance(asset_context, dict) and isinstance(asset_context.get("asset"), dict) else {}
    assignment = assignment_context.get("assignment") if isinstance(assignment_context, dict) and isinstance(assignment_context.get("assignment"), dict) else {}
    technician_obj = assignment_context.get("technician") if isinstance(assignment_context, dict) and isinstance(assignment_context.get("technician"), dict) else {}
    technician = technician_obj.get("label") or assignment.get("assign_to")
    human_review = review_required(
        asset_context,
        assignment_context,
        inventory_context,
        procurement_request,
        action_plan=action_plan,
    )
    dry_runs = dry_run_actions(actions)
    blocked = blocked_reasons(actions, cmms_push)
    status = overall_status(human_review_required=human_review, actions=actions, cmms_push=cmms_push)
    asset_code = asset.get("code") or (procurement_request or {}).get("asset_code")
    procurement_action_status = action_status(actions, "create_purchase_request", str((procurement_request or {}).get("status") or "not_required"))
    summary = {
        "schema": "cmms_orchestration_summary_v1",
        "run_id": run_id,
        "environment_code": environment_code.upper() if isinstance(environment_code, str) and environment_code.strip() else None,
        "status": status,
        "asset_code": asset_code,
        "priority": priority,
        "work_order_type": work_order_type,
        "requested_actions": requested_actions(actions, inventory_context, procurement_request),
        "steps": {
            "work_order": {
                "status": action_status(actions, "create_work_order", "planned"),
                "asset_code": asset_code,
                "priority": priority,
                "work_order_type": work_order_type,
            },
            "assignment": {
                "status": action_status(actions, "assign_work_order", str((assignment_context or {}).get("status") or "skipped")),
                "technician": technician,
                "assign_to": assignment.get("assign_to"),
                "issue_to": assignment.get("issue_to"),
                "job_type": assignment.get("job_type"),
            },
            "inventory": {
                "status": (inventory_context or {}).get("status"),
                "requires_procurement": bool((inventory_context or {}).get("requires_procurement")),
                "shortage_items": [
                    item
                    for item in ((inventory_context or {}).get("items") or [])
                    if isinstance(item, dict) and item.get("status") == "shortage"
                ],
            },
            "procurement": {
                "status": procurement_action_status,
                "line_count": len((procurement_request or {}).get("lines") or []),
                "reason": (procurement_request or {}).get("reason"),
            },
        },
        "cmms_push_status": (cmms_push or {}).get("status"),
        "dry_run_actions": dry_runs,
        "human_review_required": human_review,
        "blocked_reasons": blocked,
        "review_reasons": context_reasons(asset_context, assignment_context, inventory_context, procurement_request),
    }
    summary["operator_message"] = operator_message(
        asset_code=asset_code,
        technician=technician,
        inventory_context=inventory_context,
        procurement_request=procurement_request,
        status=status,
    )
    return summary
