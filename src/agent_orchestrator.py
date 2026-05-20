"""Small future-agent review package builder."""

from __future__ import annotations

from typing import Any


def build_agent_review(draft: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    warnings = validation.get("warnings", [])
    agents = []

    agents.append({"agent": "Intake Agent", "status": "ok", "finding": "Clear issue summary prepared."})

    if draft.get("building") or draft.get("room"):
        agents.append({"agent": "Location Agent", "status": "ok", "finding": "Location hints found."})
    else:
        agents.append({"agent": "Location Agent", "status": "review", "finding": "No reliable location found."})

    if draft.get("asset_hint"):
        agents.append({"agent": "Asset Agent", "status": "review", "finding": "Asset hint needs confirmation."})
    else:
        agents.append({"agent": "Asset Agent", "status": "review", "finding": "No asset hint found."})

    if draft.get("priority") == "P1":
        agents.append({"agent": "Priority Agent", "status": "review", "finding": "Urgency should be confirmed before dispatch."})
    else:
        agents.append({"agent": "Priority Agent", "status": "ok", "finding": "Normal priority appears reasonable."})

    if warnings:
        agents.append({"agent": "Policy Agent", "status": "review", "finding": "Warnings require human review before write-back."})
    else:
        agents.append({"agent": "Policy Agent", "status": "ok", "finding": "No blocking policy issue found."})

    needs_review = bool(warnings) or any(agent["status"] == "review" for agent in agents)
    next_action = "review_before_cmms_write" if needs_review else "ready_for_dispatcher_review"
    return {"agents": agents, "next_action": next_action}
