"""CMMS environment validation example."""

from __future__ import annotations

from typing import Any


def _candidate_strings(record: dict[str, Any]) -> list[str]:
    values = [record.get("code", ""), record.get("label", "")]
    values.extend(record.get("aliases", []))
    return [str(v).lower() for v in values if v]


def _normalize_value(value: str | None, records: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if not value:
        return None, "missing"
    value_l = value.lower().strip()
    for record in records:
        if value_l in _candidate_strings(record):
            return record["code"], None
    for record in records:
        for candidate in _candidate_strings(record):
            if candidate and candidate in value_l:
                return record["code"], None
    return value, "unknown"


def validate_environment(draft: dict[str, Any], environment: dict[str, Any]) -> dict[str, Any]:
    codes = environment.get("codes", {})
    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, Any] = dict(draft)

    for field in ["building", "priority", "trade"]:
        records = codes.get(field, [])
        normalized_value, issue = _normalize_value(draft.get(field), records)
        if normalized_value:
            normalized[field] = normalized_value
        if issue == "missing" and field in environment.get("rules", {}).get("required_fields", []):
            errors.append(f"missing_required_environment_field:{field}")
        elif issue == "unknown":
            warnings.append(f"unknown_{field}:{draft.get(field)}")

    if draft.get("asset_hint") and environment.get("rules", {}).get("allow_unknown_asset_hint", True):
        warnings.append("asset_hint_requires_human_confirmation")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "normalized": normalized}
