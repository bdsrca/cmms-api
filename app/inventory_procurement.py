"""Deterministic inventory checks and local procurement draft planning."""

from __future__ import annotations

import json
from typing import Any

from .db import db_fetchall

INVENTORY_CATEGORY = "custom:inventory_parts"


def clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def parse_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def number_or_default(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def public_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def inventory_rows(environment_code: str) -> list[Any]:
    return db_fetchall(
        """
        SELECT code, label, aliases, metadata_json
        FROM code_values
        WHERE environment_code = ? AND category = ? AND enabled = 1
        ORDER BY code
        """,
        (environment_code.upper(), INVENTORY_CATEGORY),
    )


def inventory_index(environment_code: str) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for row in inventory_rows(environment_code):
        metadata = parse_metadata(row["metadata_json"])
        code = str(row["code"]).strip()
        if not code:
            continue
        items[code.upper()] = {
            "part_number": code,
            "description": clean_text(row["label"]) or code,
            "quantity_on_hand": number_or_default(metadata.get("quantity_on_hand"), 0.0),
            "reorder_quantity": number_or_default(metadata.get("reorder_quantity"), 0.0),
            "unit": clean_text(metadata.get("unit")),
        }
    return items


def base_inventory_context(environment_code: str | None) -> dict[str, Any]:
    return {
        "schema": "cmms_inventory_context_v1",
        "environment_code": environment_code.upper() if isinstance(environment_code, str) and environment_code.strip() else None,
        "enabled": False,
        "status": "skipped",
        "requires_procurement": False,
        "requires_review": False,
        "items": [],
        "reasons": [],
    }


def likely_parts(work_order_plan: dict[str, Any]) -> list[dict[str, Any]]:
    parts = work_order_plan.get("likely_parts") if isinstance(work_order_plan, dict) else []
    return [part for part in parts if isinstance(part, dict)]


def resolve_inventory_context(work_order_plan: dict[str, Any], environment_code: str | None) -> dict[str, Any]:
    context = base_inventory_context(environment_code)
    parts = likely_parts(work_order_plan)
    if not parts:
        context["status"] = "not_required"
        context["reasons"].append("No likely parts were identified for this work order plan.")
        return context
    if not context["environment_code"]:
        context["requires_review"] = True
        context["reasons"].append("No environment_code was supplied; inventory check was skipped.")
        return context

    inventory = inventory_index(context["environment_code"])
    if not inventory:
        context["status"] = "not_configured"
        context["requires_review"] = True
        context["reasons"].append(f"No inventory parts are configured for environment {context['environment_code']}.")
        return context

    context["enabled"] = True
    unknown_parts: list[str] = []
    shortages: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for part in parts:
        part_number = clean_text(part.get("part_number") or part.get("sku") or part.get("code"))
        if not part_number:
            continue
        required = max(number_or_default(part.get("quantity"), 1.0), 1.0)
        inventory_item = inventory.get(part_number.upper())
        if not inventory_item:
            unknown_parts.append(part_number)
            items.append(
                {
                    "part_number": part_number,
                    "description": clean_text(part.get("description")),
                    "required_quantity": public_number(required),
                    "quantity_on_hand": None,
                    "shortage_quantity": None,
                    "unit": clean_text(part.get("unit")),
                    "status": "unknown",
                }
            )
            continue

        on_hand = max(number_or_default(inventory_item.get("quantity_on_hand"), 0.0), 0.0)
        shortage = max(required - on_hand, 0.0)
        item = {
            "part_number": part_number,
            "description": clean_text(part.get("description")) or inventory_item.get("description"),
            "required_quantity": public_number(required),
            "quantity_on_hand": public_number(on_hand),
            "shortage_quantity": public_number(shortage),
            "reorder_quantity": public_number(max(number_or_default(inventory_item.get("reorder_quantity"), 0.0), 0.0)),
            "unit": clean_text(part.get("unit")) or inventory_item.get("unit"),
            "status": "shortage" if shortage > 0 else "available",
        }
        items.append(item)
        if shortage > 0:
            shortages.append(item)

    context["items"] = items
    if shortages:
        context["status"] = "shortage"
        context["requires_procurement"] = True
        context["reasons"].append(f"{len(shortages)} likely part item(s) are short.")
    elif unknown_parts:
        context["status"] = "unknown_parts"
        context["requires_review"] = True
        context["reasons"].append("Some likely parts were not found in configured inventory.")
    else:
        context["status"] = "available"
        context["reasons"].append("All likely parts have enough quantity on hand.")
    return context


def build_procurement_reason(work_order_plan: dict[str, Any], shortage_items: list[dict[str, Any]]) -> str:
    asset_code = work_order_plan.get("asset_code") if isinstance(work_order_plan, dict) else None
    parts = []
    for item in shortage_items:
        parts.append(
            f"{item.get('part_number')} needs {item.get('required_quantity')}, "
            f"{item.get('quantity_on_hand')} on hand, shortage of {item.get('shortage_quantity')}"
        )
    asset_text = f" for asset {asset_code}" if asset_code else ""
    return f"Procurement draft created{asset_text} because " + "; ".join(parts) + "."


def build_procurement_request(
    run_id: Any,
    environment_code: str | None,
    work_order_plan: dict[str, Any],
    inventory_context: dict[str, Any],
) -> dict[str, Any]:
    shortage_items = [
        item
        for item in inventory_context.get("items", [])
        if isinstance(item, dict) and item.get("status") == "shortage"
    ]
    base = {
        "schema": "cmms_procurement_request_v1",
        "run_id": run_id,
        "environment_code": environment_code.upper() if isinstance(environment_code, str) and environment_code.strip() else None,
        "status": "not_required",
        "advisory_only": True,
        "fake_connector": "local_procurement_dry_run",
        "asset_code": work_order_plan.get("asset_code") if isinstance(work_order_plan, dict) else None,
        "lines": [],
        "reason": "No procurement request is required.",
        "requires_review": False,
    }
    if not shortage_items:
        if inventory_context.get("requires_review"):
            return {
                **base,
                "status": "needs_review",
                "reason": "Inventory status needs review before a procurement request can be drafted.",
                "requires_review": True,
            }
        return base

    lines = []
    for item in shortage_items:
        shortage = number_or_default(item.get("shortage_quantity"), 0.0)
        reorder_quantity = number_or_default(item.get("reorder_quantity"), 0.0)
        quantity = reorder_quantity if reorder_quantity >= shortage and reorder_quantity > 0 else shortage
        lines.append(
            {
                "part_number": item.get("part_number"),
                "description": item.get("description"),
                "quantity": public_number(quantity),
                "unit": item.get("unit"),
                "reason": (
                    f"Required {item.get('required_quantity')}; "
                    f"{item.get('quantity_on_hand')} on hand; "
                    f"shortage of {item.get('shortage_quantity')}."
                ),
            }
        )
    return {
        **base,
        "status": "drafted",
        "lines": lines,
        "reason": build_procurement_reason(work_order_plan, shortage_items),
    }
