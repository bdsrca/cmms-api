"""Code normalization suggestion helpers for controlled CMMS intake workflows."""

from __future__ import annotations

from typing import Any

from .db import db_fetchall


SUPPORTED_NORMALIZATION_FIELDS = {
    "priority": "priorities",
    "work_order_type": "work_order_types",
    "job_type": "job_type",
    "assign_to": "assign_to",
    "issue_to": "issue_to_employee_number",
}

DEFAULT_NORMALIZATION_CONFIDENCE_THRESHOLD = 0.8
MAX_REASON_LENGTH = 240
MAX_TEXT_CONTEXT_LENGTH = 500


def clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def clean_text(value: Any, max_length: int = MAX_REASON_LENGTH) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def skipped_code_normalization_block(message: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "skipped",
        "suggestions": [],
        "applied": {},
        "rejected": [],
        "message": message,
    }


def failed_code_normalization_block(message: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "status": "failed",
        "suggestions": [],
        "applied": {},
        "rejected": [],
        "message": message,
    }


def build_code_normalizer_context(
    *,
    text: str,
    text_summary: str | None = None,
    environment_code: str,
    result: dict[str, Any],
    raw_extracted_fields: dict[str, Any],
    invalid_code_candidates: dict[str, Any],
    code_values: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "environment_code": environment_code,
        "text": clean_text(text_summary if text_summary is not None else text, MAX_TEXT_CONTEXT_LENGTH),
        "result": result,
        "raw_extracted_fields": raw_extracted_fields,
        "invalid_code_candidates": invalid_code_candidates,
        "supported_fields": SUPPORTED_NORMALIZATION_FIELDS,
        "code_values": code_values,
        "instruction": "Suggest configured CMMS codes only. Do not rewrite the final payload.",
    }


def reject_suggestion(suggestion: dict[str, Any], reason_code: str) -> dict[str, Any]:
    return suggestion | {"decision": "rejected", "reason_code": reason_code}


def normalize_code_normalizer_output(
    data: dict[str, Any],
    *,
    enabled_codes_by_field: dict[str, set[str]],
) -> dict[str, Any]:
    raw_suggestions = data.get("suggestions") if isinstance(data, dict) else None
    if not isinstance(raw_suggestions, list):
        raw_suggestions = []

    accepted_candidates: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []

    for item in raw_suggestions:
        if not isinstance(item, dict):
            rejected.append({"decision": "rejected", "reason_code": "invalid_suggestion_shape"})
            continue
        field = clean_text(item.get("field"), 80)
        suggestion = {
            "field": field,
            "input_value": clean_text(item.get("input_value"), 160),
            "suggested_code": clean_text(item.get("suggested_code"), 120),
            "confidence": clamp_confidence(item.get("confidence")),
            "reason": clean_text(item.get("reason"), MAX_REASON_LENGTH),
        }
        if field not in SUPPORTED_NORMALIZATION_FIELDS:
            rejected.append(reject_suggestion(suggestion, "unsupported_field"))
            continue
        if suggestion["suggested_code"] not in enabled_codes_by_field.get(field, set()):
            rejected.append(reject_suggestion(suggestion, "code_not_configured"))
            continue
        current = accepted_candidates.get(field)
        if current is None or suggestion["confidence"] > current["confidence"]:
            if current is not None:
                rejected.append(reject_suggestion(current, "duplicate_lower_confidence"))
            accepted_candidates[field] = suggestion
        else:
            rejected.append(reject_suggestion(suggestion, "duplicate_lower_confidence"))

    return {"suggestions": list(accepted_candidates.values()), "rejected": rejected}


def apply_code_normalization_suggestions(
    *,
    result: dict[str, Any],
    invalid_code_candidates: dict[str, Any],
    normalized_model_output: dict[str, Any],
    threshold: float = DEFAULT_NORMALIZATION_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    applied: dict[str, Any] = {}
    rejected: list[dict[str, Any]] = list(normalized_model_output.get("rejected") or [])

    for suggestion in normalized_model_output.get("suggestions") or []:
        field = suggestion["field"]
        if field not in invalid_code_candidates:
            rejected.append(reject_suggestion(suggestion, "field_already_valid"))
            continue
        if suggestion["confidence"] < threshold:
            rejected.append(reject_suggestion(suggestion, "confidence_below_threshold"))
            continue
        accepted = suggestion | {"decision": "accepted"}
        suggestions.append(accepted)
        applied[field] = suggestion["suggested_code"]

    if applied:
        status = "applied"
    elif rejected:
        status = "rejected"
    else:
        status = "no_suggestions"

    return {
        "enabled": True,
        "status": status,
        "suggestions": suggestions,
        "applied": applied,
        "rejected": rejected,
    }


def load_code_values_for_normalizer(environment_code: str) -> dict[str, list[dict[str, Any]]]:
    categories = sorted(set(SUPPORTED_NORMALIZATION_FIELDS.values()))
    result: dict[str, list[dict[str, Any]]] = {category: [] for category in categories}
    for category in categories:
        rows = db_fetchall(
            """
            SELECT code, label, aliases
            FROM code_values
            WHERE environment_code = ? AND category = ? AND enabled = 1
            ORDER BY code
            """,
            (environment_code, category),
        )
        result[category] = [
            {"code": row["code"], "label": row["label"], "aliases": row["aliases"] or ""}
            for row in rows
        ]
    return result


def enabled_codes_by_field(code_values: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for field, category in SUPPORTED_NORMALIZATION_FIELDS.items():
        result[field] = {str(row["code"]) for row in code_values.get(category, []) if row.get("code")}
    return result


def code_value_matches(value: Any, rows: list[dict[str, Any]]) -> bool:
    text = clean_text(value, 240).casefold()
    if not text:
        return False
    for row in rows:
        candidates = [row.get("code"), row.get("label")]
        aliases = row.get("aliases") or ""
        candidates.extend(part.strip() for part in str(aliases).split(",") if part.strip())
        for candidate in candidates:
            if clean_text(candidate, 240).casefold() == text:
                return True
    return False


def collect_invalid_code_candidates(
    *,
    result: dict[str, Any],
    existing_candidates: dict[str, Any],
    code_values: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    candidates = dict(existing_candidates or {})
    for field, category in SUPPORTED_NORMALIZATION_FIELDS.items():
        if field in candidates:
            continue
        value = result.get(field)
        if not clean_text(value, 240):
            continue
        if not code_value_matches(value, code_values.get(category, [])):
            candidates[field] = value
    return candidates
