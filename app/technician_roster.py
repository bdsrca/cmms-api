"""Deterministic on-duty technician lookup for controlled assignment planning."""

from __future__ import annotations

import json
from typing import Any

from .db import db_fetchall

ROSTER_CATEGORY = "technician_roster"


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


def split_aliases(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    return [alias.strip() for alias in value.split(",") if alias.strip()]


def text_has_assignment_intent(request_text: str) -> bool:
    text = (request_text or "").lower()
    cues = [
        "assign",
        "assigned",
        "dispatch",
        "on-duty",
        "on duty",
        "tonight",
        "night shift",
        "值班",
        "今晚",
        "分配",
        "派给",
    ]
    return any(cue in text for cue in cues)


def requested_shift(request_text: str) -> str | None:
    text = (request_text or "").lower()
    if any(cue in text for cue in ["tonight", "night shift", "overnight", "今晚", "夜班"]):
        return "night"
    return None


def normalize_trade(value: Any) -> str | None:
    text = clean_text(value)
    return text.upper() if text else None


def metadata_trades(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("trades") or metadata.get("trade")
    if isinstance(raw, list):
        return [str(item).upper() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [item.strip().upper() for item in raw.split(",") if item.strip()]
    return []


def technician_rows(environment_code: str) -> list[Any]:
    return db_fetchall(
        """
        SELECT code, label, aliases, metadata_json
        FROM code_values
        WHERE environment_code = ? AND category = ? AND enabled = 1
        ORDER BY code
        """,
        (environment_code.upper(), ROSTER_CATEGORY),
    )


def technician_from_row(row: Any) -> dict[str, Any]:
    metadata = parse_metadata(row["metadata_json"])
    return {
        "code": row["code"],
        "label": row["label"],
        "aliases": split_aliases(row["aliases"]),
        "shift": clean_text(metadata.get("shift")),
        "trades": metadata_trades(metadata),
        "assign_to": clean_text(metadata.get("assign_to")) or row["label"],
        "issue_to": clean_text(metadata.get("issue_to")),
        "job_type": clean_text(metadata.get("job_type")),
    }


def technician_is_eligible(technician: dict[str, Any], shift: str | None, trade: str | None) -> bool:
    if shift and str(technician.get("shift") or "").lower() != shift.lower():
        return False
    normalized_trade = normalize_trade(trade)
    trades = technician.get("trades") if isinstance(technician.get("trades"), list) else []
    if normalized_trade and trades and normalized_trade not in trades:
        return False
    return True


def base_assignment_context(environment_code: str | None) -> dict[str, Any]:
    return {
        "schema": "cmms_assignment_context_v1",
        "environment_code": environment_code.upper() if isinstance(environment_code, str) and environment_code.strip() else None,
        "enabled": False,
        "status": "skipped",
        "requires_review": False,
        "technician": None,
        "candidates": [],
        "assignment": {"assign_to": None, "issue_to": None, "job_type": None},
        "reasons": [],
    }


def public_technician(technician: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": technician.get("code"),
        "label": technician.get("label"),
        "aliases": technician.get("aliases") if isinstance(technician.get("aliases"), list) else [],
        "shift": technician.get("shift"),
        "trades": technician.get("trades") if isinstance(technician.get("trades"), list) else [],
    }


def assignment_for_technician(technician: dict[str, Any]) -> dict[str, Any]:
    return {
        "assign_to": technician.get("assign_to"),
        "issue_to": technician.get("issue_to"),
        "job_type": technician.get("job_type"),
    }


def resolve_assignment_context(request_text: str, environment_code: str | None, trade: str | None = None) -> dict[str, Any]:
    context = base_assignment_context(environment_code)
    if not text_has_assignment_intent(request_text):
        context["reasons"].append("No assignment intent was detected in the request.")
        return context
    if not context["environment_code"]:
        context["requires_review"] = True
        context["reasons"].append("No environment_code was supplied; assignment resolution was skipped.")
        return context

    technicians = [technician_from_row(row) for row in technician_rows(context["environment_code"])]
    if not technicians:
        context["status"] = "not_configured"
        context["requires_review"] = True
        context["reasons"].append(f"No technician roster is configured for environment {context['environment_code']}.")
        return context

    shift = requested_shift(request_text)
    matches = [technician for technician in technicians if technician_is_eligible(technician, shift, trade)]
    context["enabled"] = True
    context["candidates"] = [public_technician(technician) for technician in matches]

    if not matches:
        context["status"] = "not_found"
        context["requires_review"] = True
        context["reasons"].append("No configured technician matched the requested shift and trade.")
        return context
    if len(matches) > 1:
        context["status"] = "ambiguous"
        context["requires_review"] = True
        context["reasons"].append("Multiple configured technicians matched the requested shift and trade.")
        return context

    technician = matches[0]
    context["status"] = "resolved"
    context["technician"] = public_technician(technician)
    context["assignment"] = assignment_for_technician(technician)
    context["reasons"].append(f"Matched on-duty technician {technician['code']}.")
    return context


def apply_assignment_to_payload(payload: dict[str, Any], assignment_context: dict[str, Any]) -> dict[str, Any]:
    if assignment_context.get("status") != "resolved":
        return payload
    assignment = assignment_context.get("assignment") if isinstance(assignment_context.get("assignment"), dict) else {}
    updates = {
        field: assignment.get(field)
        for field in ("assign_to", "issue_to", "job_type")
        if clean_text(assignment.get(field))
    }
    return payload | updates
