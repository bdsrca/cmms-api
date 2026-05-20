"""Simple output contract validator."""

from __future__ import annotations

from typing import Any

TYPE_MAP = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}

DEFAULT_CONTRACT = {
    "required": ["summary", "priority", "trade", "confidence"],
    "types": {
        "summary": "string",
        "priority": "string",
        "trade": "string",
        "building": "string",
        "room": "string",
        "asset_hint": "string",
        "location_hint": "string",
        "confidence": "number",
    },
    "allow_extra_fields": False,
}


def validate_contract(output: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or DEFAULT_CONTRACT
    errors: list[str] = []
    warnings: list[str] = []
    required = contract.get("required", [])
    types = contract.get("types", {})

    for field in required:
        if field not in output or output.get(field) in (None, ""):
            errors.append(f"missing_required:{field}")

    for field, expected_name in types.items():
        if field in output and output[field] is not None:
            expected = TYPE_MAP.get(expected_name)
            if expected and not isinstance(output[field], expected):
                errors.append(f"invalid_type:{field}:{expected_name}")

    if not contract.get("allow_extra_fields", False):
        extra = set(output) - set(types)
        for field in sorted(extra):
            warnings.append(f"unexpected_field:{field}")

    return {"valid": not errors, "errors": errors, "warnings": warnings}
