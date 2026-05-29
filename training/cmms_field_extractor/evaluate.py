"""Evaluation metrics for CMMS field extractor model outputs."""

from __future__ import annotations

import json
from typing import Any

from .schema import REQUIRED_ASSISTANT_KEYS, assistant_payload_errors


LOCATION_KEYS = ("building", "room")
REQUIRED_FIELD_KEYS = ("request_type", "building", "room", "priority", "summary")


def _rate(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


def _failure(example_id: str, category: str) -> dict[str, str]:
    return {"id": example_id, "category": category}


def evaluate_predictions(examples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(examples)
    parsed_count = 0
    contract_valid_count = 0
    required_field_matches = 0
    required_field_total = 0
    per_field_matches = {key: 0 for key in REQUIRED_FIELD_KEYS}
    per_field_totals = {key: 0 for key in REQUIRED_FIELD_KEYS}
    priority_matches = 0
    priority_total = 0
    hallucinated_location_count = 0
    unsafe_claim_count = 0
    failures: list[dict[str, str]] = []

    for example in examples:
        example_id = str(example.get("id", "unknown"))
        expected = example["expected"]
        prediction_text = example["prediction"]

        try:
            prediction = json.loads(prediction_text)
        except json.JSONDecodeError:
            failures.append(_failure(example_id, "invalid_json"))
            continue

        if not isinstance(prediction, dict):
            failures.append(_failure(example_id, "invalid_json_object"))
            continue

        parsed_count += 1
        schema_errors = assistant_payload_errors(prediction)
        if not schema_errors:
            contract_valid_count += 1
        else:
            failures.append(_failure(example_id, "contract_mismatch"))

        for key in REQUIRED_FIELD_KEYS:
            required_field_total += 1
            per_field_totals[key] += 1
            if prediction.get(key) == expected.get(key):
                required_field_matches += 1
                per_field_matches[key] += 1

        if expected.get("priority") is not None:
            priority_total += 1
            if prediction.get("priority") == expected.get("priority"):
                priority_matches += 1
            else:
                failures.append(_failure(example_id, "wrong_priority"))

        for key in LOCATION_KEYS:
            if expected.get(key) is None and prediction.get(key):
                hallucinated_location_count += 1
                failures.append(_failure(example_id, f"hallucinated_{key}"))

        if any(error.startswith("assistant.unsafe_claim") for error in schema_errors):
            unsafe_claim_count += 1
            failures.append(_failure(example_id, "unsafe_claim"))

        for extra_key in set(prediction) - REQUIRED_ASSISTANT_KEYS:
            failures.append(_failure(example_id, f"unexpected_extra_field:{extra_key}"))

    return {
        "total": total,
        "json_parse_success_rate": _rate(parsed_count, total),
        "contract_valid_rate": _rate(contract_valid_count, total),
        "required_field_accuracy": _rate(required_field_matches, required_field_total),
        "per_field_accuracy": {
            key: _rate(per_field_matches[key], per_field_totals[key])
            for key in sorted(REQUIRED_FIELD_KEYS)
        },
        "priority_accuracy": _rate(priority_matches, priority_total),
        "hallucinated_location_count": hallucinated_location_count,
        "unsafe_claim_count": unsafe_claim_count,
        "failures": failures,
    }
