"""Deterministic private LLM gateway mock.

A real implementation would call a private model endpoint after auth, quota, and policy checks.
This mock keeps the repository safe and testable without secrets.
"""

from __future__ import annotations

import re
from typing import Any


def extract_work_request(text: str) -> dict[str, Any]:
    body = text.lower()
    priority = "NORMAL"
    if any(word in body for word in ["urgent", "emergency", "asap", "leak", "flood"]):
        priority = "P1"

    trade = "GENERAL"
    if any(word in body for word in ["water", "leak", "pipe", "drain", "toilet", "sink"]):
        trade = "PLUMBING"
    elif any(word in body for word in ["air", "heat", "hot", "cold", "hvac", "ahu", "air handler"]):
        trade = "HVAC"
    elif any(word in body for word in ["power", "outlet", "light", "breaker"]):
        trade = "ELECTRICAL"

    building = None
    if "arc" in body:
        building = "ARC"
    elif "science" in body:
        building = "SCI"

    room_match = re.search(r"room\s+([a-z0-9-]+)", body)
    room = room_match.group(1).upper() if room_match else None

    asset_hint = None
    for hint in ["air handler", "ahu", "pump", "fan", "ceiling", "outlet"]:
        if hint in body:
            asset_hint = hint.upper() if hint == "ahu" else hint
            break

    summary = text.strip().rstrip(".")
    if len(summary) > 140:
        summary = summary[:137] + "..."

    return {
        "summary": summary,
        "priority": priority,
        "trade": trade,
        "building": building,
        "room": room,
        "asset_hint": asset_hint,
        "location_hint": " ".join(x for x in [building, room] if x) or None,
        "confidence": 0.82 if trade != "GENERAL" else 0.55,
    }
