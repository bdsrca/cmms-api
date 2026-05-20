"""Targeted analytics from safe API events."""

from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_endpoint = Counter(event.get("endpoint") for event in events)
    by_status = Counter(event.get("status") for event in events)
    by_environment = Counter(event.get("environment_code") for event in events)
    return {
        "total_events": len(events),
        "by_endpoint": dict(by_endpoint),
        "by_status": dict(by_status),
        "by_environment": dict(by_environment),
        "recommendations": _recommendations(events),
    }


def _recommendations(events: list[dict[str, Any]]) -> list[str]:
    recommendations: list[str] = []
    validation_failures = [e for e in events if e.get("status") in {"validation_warning", "validation_error"}]
    if validation_failures:
        recommendations.append("Review aliases and validation rules for environments with repeated warnings.")
    quota_hits = [e for e in events if e.get("status") == "quota_exceeded"]
    if quota_hits:
        recommendations.append("Increase quota only after reviewing whether the token is used for real pilot workflows.")
    if not recommendations:
        recommendations.append("No immediate data-quality action found in the sample events.")
    return recommendations
