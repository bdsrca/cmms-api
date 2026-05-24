# Code Normalization Suggestion Agent v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded Code Normalization Suggestion Agent to `cmms-intake` so multilingual or ambiguous extracted code fields can be suggested, accepted, rejected, traced, and displayed without bypassing deterministic validation.

**Architecture:** Implement pure deterministic helpers first in `app/code_normalizer.py`, then wire the helper into the `cmms-intake` workflow after output contract validation and before environment validation. Draft generation moves after normalization and environment validation so drafts use the final visible values. The agent suggests codes only; Python decides whether suggestions are accepted.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Pydantic, existing prompt version manager, existing workflow trace, existing unittest suite.

---

## Guardrails

- Do not add Router Agent.
- Do not add autonomous planning.
- Do not add LLM judge.
- Do not add generic `/chat`.
- Do not add backend audio upload.
- Do not expose Ollama directly.
- Do not add new CMMS write-back routes.
- Do not send emails.
- Do not let the LLM directly mutate final payload values.
- Do not silently normalize fields. Accepted and rejected suggestions must be visible.

---

## File Structure

- Create `app/code_normalizer.py`
  - Owns pure code-normalizer context building, model-output normalization, deterministic acceptance/rejection, skipped blocks, and failed blocks.

- Modify `app/config.py`
  - Fix default `issue_to` validation category.
  - Add `cmms-code-normalizer` to supported prompt endpoints.
  - Seed the default active normalizer prompt.

- Modify `app/ai_endpoints.py`
  - Preserve raw extracted fields and invalid code candidates.
  - Insert `code_normalization_suggestion_agent` trace step.
  - Move draft generation after code normalization and environment validation.
  - Include `code_normalization` in the returned response.

- Modify `app/models.py`
  - Add `code_normalization` to `IntakeResponse`.

- Modify `app/ui.py`
  - Add a compact Code Normalization panel in Test Console output.

- Create `tests/test_code_normalizer.py`
  - Pure function tests for `app/code_normalizer.py`.

- Create `tests/test_code_normalizer_intake_api.py`
  - Pipeline and response tests for `cmms-intake`.

- Create `tests/test_code_normalizer_ui.py`
  - Verify Test Console renders the code-normalization block.

- Create `docs/implementation/54-code-normalization-suggestion-agent-v1.md`
  - Document implementation decisions, safety boundary, tests, and known limits.

---

## Task 1: Fix Issue-To Category Mapping

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_code_normalizer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_code_normalizer.py` with this initial test:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.environments import seed_default_environment
from app.validation_rules import get_validation_rules


class CodeNormalizerConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_default_issue_to_rule_uses_employee_number_category(self) -> None:
        rules = get_validation_rules("DEFAULT")
        issue_to = next(rule for rule in rules if rule["field_name"] == "issue_to")

        self.assertEqual(issue_to["code_category"], "issue_to_employee_number")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerConfigTests.test_default_issue_to_rule_uses_employee_number_category
```

Expected: FAIL because the current default rule maps `issue_to` to `issue_to`.

- [ ] **Step 3: Implement the mapping fix**

In `app/config.py`, change the default validation rule row for `issue_to` from:

```python
("issue_to", "Issue To", False, "issue_to", True, False, "warning", 60),
```

to:

```python
("issue_to", "Issue To", False, "issue_to_employee_number", True, False, "warning", 60),
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerConfigTests.test_default_issue_to_rule_uses_employee_number_category
```

Expected: PASS.

---

## Task 2: Preserve Raw Extraction and Invalid Code Candidates

**Files:**
- Modify: `app/ai_endpoints.py`
- Test: `tests/test_code_normalizer.py`

- [ ] **Step 1: Add failing extraction-preservation tests**

Append these tests to `tests/test_code_normalizer.py`:

```python
from app.ai_endpoints import validate_extracted_fields


class CodeNormalizerExtractionTests(unittest.TestCase):
    def test_invalid_priority_preserves_raw_value_and_candidate(self) -> None:
        result = validate_extracted_fields(
            {
                "request_type": "Plumbing",
                "building": "ARC",
                "room": "205",
                "priority": "urgent phrase",
                "summary": "Water leak in ARC 205.",
                "missing_fields": [],
                "needs_human_review": False,
                "confidence": 0.9,
            },
            valid_buildings=["ARC"],
            valid_priorities=["LOW", "NORMAL", "URGENT"],
        )

        self.assertEqual(result["priority"], "NORMAL")
        self.assertEqual(result["raw_extracted_fields"]["priority"], "urgent phrase")
        self.assertEqual(result["validated_fields"]["priority"], "NORMAL")
        self.assertEqual(result["invalid_code_candidates"]["priority"], "urgent phrase")

    def test_valid_priority_does_not_create_invalid_candidate(self) -> None:
        result = validate_extracted_fields(
            {
                "request_type": "HVAC",
                "building": "ARC",
                "room": "205",
                "priority": "URGENT",
                "summary": "ARC 205 is too hot.",
                "missing_fields": [],
                "needs_human_review": False,
                "confidence": 0.8,
            },
            valid_buildings=["ARC"],
            valid_priorities=["LOW", "NORMAL", "URGENT"],
        )

        self.assertEqual(result["priority"], "URGENT")
        self.assertEqual(result["raw_extracted_fields"]["priority"], "URGENT")
        self.assertEqual(result["validated_fields"]["priority"], "URGENT")
        self.assertNotIn("priority", result["invalid_code_candidates"])
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerExtractionTests
```

Expected: FAIL because the returned dict does not yet include `raw_extracted_fields`, `validated_fields`, or `invalid_code_candidates`.

- [ ] **Step 3: Implement preservation in `validate_extracted_fields`**

In `app/ai_endpoints.py`, update `validate_extracted_fields` so it captures raw fields before fallback:

```python
def clean_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
```

Inside `validate_extracted_fields`, keep the existing public output keys, but add this before final return:

```python
raw_extracted_fields = {
    "request_type": data.get("request_type"),
    "building": clean_optional_text(data.get("building")),
    "room": clean_optional_text(data.get("room")),
    "priority": clean_optional_text(data.get("priority")),
    "summary": clean_optional_text(data.get("summary")) or "",
}
invalid_code_candidates: dict[str, Any] = {}
```

Change the priority handling from direct fallback to:

```python
priority = raw_extracted_fields["priority"]
if priority not in allowed_priorities:
    if priority:
        invalid_code_candidates["priority"] = priority
    priority = "NORMAL"
```

Before returning, build:

```python
validated_fields = {
    "request_type": request_type,
    "building": building,
    "room": room,
    "priority": priority or "NORMAL",
    "summary": summary,
}
```

Add these fields to the return dict:

```python
"raw_extracted_fields": raw_extracted_fields,
"validated_fields": validated_fields,
"invalid_code_candidates": invalid_code_candidates,
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerExtractionTests
```

Expected: PASS.

---

## Task 3: Create Pure Code Normalizer Module

**Files:**
- Create: `app/code_normalizer.py`
- Test: `tests/test_code_normalizer.py`

- [ ] **Step 1: Write failing pure-function tests**

Append this test class to `tests/test_code_normalizer.py`:

```python
from app.code_normalizer import (
    apply_code_normalization_suggestions,
    build_code_normalizer_context,
    failed_code_normalization_block,
    normalize_code_normalizer_output,
    skipped_code_normalization_block,
)


class CodeNormalizerPureFunctionTests(unittest.TestCase):
    def test_skipped_block_is_stable(self) -> None:
        block = skipped_code_normalization_block("Skipped because output contract validation failed.")

        self.assertEqual(block["enabled"], False)
        self.assertEqual(block["status"], "skipped")
        self.assertEqual(block["suggestions"], [])
        self.assertEqual(block["applied"], {})
        self.assertEqual(block["rejected"], [])
        self.assertEqual(block["message"], "Skipped because output contract validation failed.")

    def test_failed_block_is_stable(self) -> None:
        block = failed_code_normalization_block("Model returned invalid JSON")

        self.assertEqual(block["enabled"], True)
        self.assertEqual(block["status"], "failed")
        self.assertIn("Model returned invalid JSON", block["message"])

    def test_context_includes_raw_fields_candidates_and_configured_codes(self) -> None:
        context = build_code_normalizer_context(
            text="This is urgent.",
            environment_code="DEFAULT",
            result={"priority": "NORMAL", "summary": "Leak."},
            raw_extracted_fields={"priority": "urgent phrase"},
            invalid_code_candidates={"priority": "urgent phrase"},
            code_values={"priorities": [{"code": "URGENT", "label": "Urgent", "aliases": "asap"}]},
        )

        self.assertEqual(context["environment_code"], "DEFAULT")
        self.assertEqual(context["raw_extracted_fields"]["priority"], "urgent phrase")
        self.assertEqual(context["invalid_code_candidates"]["priority"], "urgent phrase")
        self.assertEqual(context["code_values"]["priorities"][0]["code"], "URGENT")
        self.assertLessEqual(len(context["text"]), 500)

    def test_normalize_model_output_rejects_unknown_fields_and_bad_codes(self) -> None:
        normalized = normalize_code_normalizer_output(
            {
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "URGENT", "confidence": 0.91, "reason": "Urgent wording."},
                    {"field": "building", "input_value": "arc", "suggested_code": "ARC", "confidence": 0.99, "reason": "Unsupported in v1."},
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "NOT_CONFIGURED", "confidence": 0.9, "reason": "Bad code."},
                ]
            },
            enabled_codes_by_field={"priority": {"URGENT", "NORMAL", "LOW"}},
        )

        self.assertEqual(len(normalized["suggestions"]), 1)
        self.assertEqual(normalized["suggestions"][0]["field"], "priority")
        self.assertEqual(normalized["suggestions"][0]["suggested_code"], "URGENT")
        self.assertEqual(len(normalized["rejected"]), 2)

    def test_apply_accepts_configured_high_confidence_invalid_priority(self) -> None:
        block = apply_code_normalization_suggestions(
            result={"priority": "NORMAL", "summary": "Leak."},
            invalid_code_candidates={"priority": "urgent phrase"},
            normalized_model_output={
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "URGENT", "confidence": 0.86, "reason": "Urgent wording."}
                ],
                "rejected": [],
            },
            threshold=0.8,
        )

        self.assertEqual(block["status"], "applied")
        self.assertEqual(block["applied"], {"priority": "URGENT"})
        self.assertEqual(block["suggestions"][0]["decision"], "accepted")

    def test_apply_rejects_low_confidence_and_already_valid_field(self) -> None:
        low = apply_code_normalization_suggestions(
            result={"priority": "NORMAL"},
            invalid_code_candidates={"priority": "urgent phrase"},
            normalized_model_output={
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "URGENT", "confidence": 0.4, "reason": "Weak."}
                ],
                "rejected": [],
            },
            threshold=0.8,
        )
        already_valid = apply_code_normalization_suggestions(
            result={"priority": "URGENT"},
            invalid_code_candidates={},
            normalized_model_output={
                "suggestions": [
                    {"field": "priority", "input_value": "urgent phrase", "suggested_code": "NORMAL", "confidence": 0.9, "reason": "Wrong."}
                ],
                "rejected": [],
            },
            threshold=0.8,
        )

        self.assertEqual(low["status"], "rejected")
        self.assertEqual(low["rejected"][0]["reason_code"], "confidence_below_threshold")
        self.assertEqual(already_valid["rejected"][0]["reason_code"], "field_already_valid")
```

- [ ] **Step 2: Run pure-function tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerPureFunctionTests
```

Expected: FAIL because `app.code_normalizer` does not exist.

- [ ] **Step 3: Create `app/code_normalizer.py`**

Create `app/code_normalizer.py` with:

```python
"""Code normalization suggestion helpers for controlled CMMS intake workflows."""

from __future__ import annotations

from typing import Any


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
    environment_code: str,
    result: dict[str, Any],
    raw_extracted_fields: dict[str, Any],
    invalid_code_candidates: dict[str, Any],
    code_values: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "environment_code": environment_code,
        "text": clean_text(text, MAX_TEXT_CONTEXT_LENGTH),
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
```

- [ ] **Step 4: Run pure-function tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerPureFunctionTests
```

Expected: PASS.

---

## Task 4: Seed `cmms-code-normalizer` Prompt Endpoint

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_code_normalizer.py`

- [ ] **Step 1: Write failing prompt seed tests**

Append to `tests/test_code_normalizer.py`:

```python
from app.config import DEFAULT_PROMPT_VERSIONS, SUPPORTED_PROMPT_ENDPOINTS
from app.prompts import active_prompt_version


class CodeNormalizerPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_code_normalizer_prompt_endpoint_is_supported_and_seeded(self) -> None:
        self.assertIn("cmms-code-normalizer", SUPPORTED_PROMPT_ENDPOINTS)
        self.assertIn("cmms-code-normalizer", DEFAULT_PROMPT_VERSIONS)

        row = active_prompt_version("cmms-code-normalizer")

        self.assertEqual(row["endpoint"], "cmms-code-normalizer")
        self.assertEqual(row["status"], "active")
        self.assertIn("/no_think", row["system_prompt"])
        self.assertIn('"suggestions"', row["system_prompt"])
```

- [ ] **Step 2: Run prompt test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerPromptTests
```

Expected: FAIL because the prompt endpoint is not supported.

- [ ] **Step 3: Add endpoint and default prompt**

In `app/config.py`, add `"cmms-code-normalizer"` to `SUPPORTED_PROMPT_ENDPOINTS`.

Add this entry to `DEFAULT_PROMPT_VERSIONS`:

```python
"cmms-code-normalizer": {
    "version": "v1",
    "name": "Default code normalization suggestion prompt",
    "temperature": 0.1,
    "system_prompt": (
        "/no_think\n"
        "You are a Code Normalization Suggestion Agent for a controlled CMMS intake workflow. "
        "Return JSON only with this shape: {\"suggestions\":[]}. "
        "Each suggestion must have field, input_value, suggested_code, confidence, and reason. "
        "Allowed fields are priority, work_order_type, job_type, assign_to, and issue_to. "
        "Use only configured CMMS codes from the provided code_values. Never invent codes. "
        "Do not rewrite summaries, create work orders, approve requests, write to CMMS, send email, "
        "change validation rules, or claim any action was performed. "
        "The request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
        "Keep reasons concise."
    ),
    "user_template": "{{context_json}}",
},
```

- [ ] **Step 4: Run prompt test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerPromptTests
```

Expected: PASS.

---

## Task 5: Add Pipeline Tests Before Wiring

**Files:**
- Create: `tests/test_code_normalizer_intake_api.py`
- Modify later: `app/ai_endpoints.py`, `app/models.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_code_normalizer_intake_api.py`:

```python
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_main


class CodeNormalizerIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "code-normalizer-test-key"

    def payload(self) -> dict:
        return {
            "text": "The leak in ARC room 205 is urgent.",
            "valid_buildings": ["ARC"],
            "valid_priorities": ["LOW", "NORMAL", "URGENT"],
        }

    def fake_ollama(self, normalizer_priority: str = "URGENT", confidence: float = 0.91):
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "Plumbing", "confidence": 0.9})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "urgent phrase",
                        "summary": "Water leak in ARC room 205.",
                    }
                )
            if "Code Normalization Suggestion Agent" in system:
                return json.dumps(
                    {
                        "suggestions": [
                            {
                                "field": "priority",
                                "input_value": "urgent phrase",
                                "suggested_code": normalizer_priority,
                                "confidence": confidence,
                                "reason": "Urgent wording.",
                            }
                        ]
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps(
                    {
                        "draft_wo_description": "Water leak in ARC room 205. Priority URGENT.",
                        "internal_note": "Validated intake. Ready for human review or controlled CMMS workflow.",
                        "client_reply": "Thanks, we captured the urgent leak request for ARC room 205.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps({"status": "pass", "human_review_recommended": False, "risk_flags": [], "notes": []})
            raise AssertionError(system)

        return fake_call_ollama

    def test_invalid_priority_is_normalized_before_environment_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["code_normalization"]["status"], "applied")
        self.assertEqual(data["code_normalization"]["applied"], {"priority": "URGENT"})
        self.assertEqual(data["result"]["priority"], "URGENT")
        self.assertEqual(data["ai_validation"]["normalized"].get("priority"), "URGENT")
        self.assertEqual(data["review"]["status"], "pass")

    def test_low_confidence_suggestion_is_rejected(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama(confidence=0.2)

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )

        data = response.json()
        self.assertEqual(data["code_normalization"]["status"], "rejected")
        self.assertEqual(data["code_normalization"]["rejected"][0]["reason_code"], "confidence_below_threshold")

    def test_contract_failure_skips_normalizer(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()
        contract_failure = {
            "valid": False,
            "errors": [{"field": "summary", "message": "missing"}],
            "warnings": [],
            "contract_version": "v1",
            "normalized_payload": {},
        }

        with patch("app.ai_endpoints.validate_output_contract", return_value=contract_failure):
            with TestClient(app_main.app) as client:
                response = client.post(
                    "/api/ai/cmms-intake",
                    headers={"x-api-key": "code-normalizer-test-key"},
                    json=self.payload(),
                )

        data = response.json()
        self.assertEqual(data["code_normalization"]["status"], "skipped")
        self.assertEqual(data["ai_validation"]["status"], "not_run")

    def test_response_model_exposes_code_normalization(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )

        self.assertIn("code_normalization", response.json())
```

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer_intake_api
```

Expected: FAIL because the pipeline has no code normalizer step and response model has no `code_normalization`.

---

## Task 6: Add Code Values Loader for Normalizer

**Files:**
- Modify: `app/code_normalizer.py`
- Test: `tests/test_code_normalizer.py`

- [ ] **Step 1: Add failing code-value loader test**

Append to `tests/test_code_normalizer.py`:

```python
from app.code_normalizer import enabled_codes_by_field, load_code_values_for_normalizer


class CodeNormalizerCodeValueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()
        db.db_execute(
            """
            INSERT INTO code_values
            (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
            VALUES ('DEFAULT', 'priorities', 'URGENT', 'Urgent', 'asap', NULL, 'Manual', 1, 'now', 'now')
            """
        )

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_load_code_values_and_enabled_codes_by_field(self) -> None:
        values = load_code_values_for_normalizer("DEFAULT")
        codes = enabled_codes_by_field(values)

        self.assertEqual(values["priorities"][0]["code"], "URGENT")
        self.assertEqual(codes["priority"], {"URGENT"})
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerCodeValueTests
```

Expected: FAIL because loader helpers do not exist.

- [ ] **Step 3: Implement loader helpers**

Add to `app/code_normalizer.py`:

```python
from .db import db_fetchall


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
```

- [ ] **Step 4: Run code-value tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer.CodeNormalizerCodeValueTests
```

Expected: PASS.

---

## Task 7: Wire Normalizer Into `cmms-intake`

**Files:**
- Modify: `app/ai_endpoints.py`
- Modify: `app/models.py`
- Test: `tests/test_code_normalizer_intake_api.py`

- [ ] **Step 1: Extend `IntakeResponse`**

In `app/models.py`, add this field to `IntakeResponse` near `ai_validation` and `review`:

```python
code_normalization: dict[str, Any] | None = None
```

- [ ] **Step 2: Import normalizer helpers in `app/ai_endpoints.py`**

Add imports:

```python
from .code_normalizer import (
    apply_code_normalization_suggestions,
    build_code_normalizer_context,
    enabled_codes_by_field,
    failed_code_normalization_block,
    load_code_values_for_normalizer,
    normalize_code_normalizer_output,
    skipped_code_normalization_block,
)
```

Also import `prompt_messages` if it is not already available in the file.

- [ ] **Step 3: Preserve raw extraction data from `validate_intake`**

Update `validate_intake` so it returns the extra extraction metadata. Change the return type to include a fifth value:

```python
return validated["request_type"], validated["confidence"], fields, validation, {
    "raw_extracted_fields": validated.get("raw_extracted_fields", {}),
    "validated_fields": validated.get("validated_fields", {}),
    "invalid_code_candidates": validated.get("invalid_code_candidates", {}),
}
```

Update the call site in `cmms_intake`:

```python
request_type, confidence, fields, validation, extraction_context = validate_intake(...)
```

- [ ] **Step 4: Move draft generation out of model extraction**

Inside the `model_extraction` step, keep only:

- classifier call
- field extractor call
- `validate_intake`
- metadata extraction
- result payload construction

Remove the draft-generator LLM call from the `model_extraction` section. Keep `intake_messages["draft_generator"]` available for later.

Update `model_call_count` in the model extraction trace output from `3` to `2`.

- [ ] **Step 5: Insert `code_normalization_suggestion_agent` after output contract validation**

After `contract_block` is built and before `environment_validation`, insert:

```python
current_step = start_workflow_step(
    run_id,
    "code_normalization_suggestion_agent",
    35,
    input_summary=f"contract_valid={contract_validation['valid']} environment={env_code or 'none'}",
)
if env_code and contract_validation["valid"]:
    try:
        code_values = load_code_values_for_normalizer(env_code)
        normalizer_context = build_code_normalizer_context(
            text=payload.text,
            environment_code=env_code,
            result=contract_validation["normalized_payload"],
            raw_extracted_fields=extraction_context["raw_extracted_fields"],
            invalid_code_candidates=extraction_context["invalid_code_candidates"],
            code_values=code_values,
        )
        normalizer_messages, normalizer_prompt_meta = prompt_messages(
            "cmms-code-normalizer",
            {"context_json": normalizer_context},
        )
        db_execute(
            "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
            (
                normalizer_prompt_meta["model"],
                f"{normalizer_prompt_meta['prompt_id']}:{normalizer_prompt_meta['prompt_version']}",
                current_step,
            ),
        )
        normalizer_raw = await call_ollama_func(
            normalizer_messages,
            temperature=normalizer_prompt_meta["temperature"],
            model=normalizer_prompt_meta["model"],
        )
        normalizer_data = parse_json_response(normalizer_raw)
        normalized_suggestions = normalize_code_normalizer_output(
            normalizer_data,
            enabled_codes_by_field=enabled_codes_by_field(code_values),
        )
        code_normalization = apply_code_normalization_suggestions(
            result=contract_validation["normalized_payload"],
            invalid_code_candidates=extraction_context["invalid_code_candidates"],
            normalized_model_output=normalized_suggestions,
        )
        if code_normalization["applied"]:
            contract_validation["normalized_payload"] = contract_validation["normalized_payload"] | code_normalization["applied"]
            fields = fields | {key: value for key, value in code_normalization["applied"].items() if key in fields}
        normalizer_step_status = "warning" if code_normalization["rejected"] and not code_normalization["applied"] else "passed"
        finish_workflow_step(
            current_step,
            normalizer_step_status,
            output_summary=(
                f"status={code_normalization['status']} "
                f"suggestions={len(code_normalization['suggestions'])} "
                f"rejected={len(code_normalization['rejected'])}"
            ),
            output_json={
                "status": code_normalization["status"],
                "suggestion_count": len(code_normalization["suggestions"]),
                "accepted_count": len(code_normalization["applied"]),
                "rejected_count": len(code_normalization["rejected"]),
                "rejected_reasons": sorted(
                    {
                        item.get("reason_code", "unknown")
                        for item in code_normalization["rejected"]
                        if isinstance(item, dict)
                    }
                ),
                "prompt_id": normalizer_prompt_meta["prompt_id"],
                "prompt_version": normalizer_prompt_meta["prompt_version"],
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        code_normalization = failed_code_normalization_block("Code normalization failed.")
        finish_workflow_step(
            current_step,
            "failed",
            output_summary="Code normalization failed.",
            output_json={"status": "failed", "message": str(exc)[:200]},
        )
else:
    message = "Skipped because output contract validation failed." if env_code else "Skipped because no environment_code was supplied."
    code_normalization = skipped_code_normalization_block(message)
    finish_workflow_step(
        current_step,
        "skipped",
        output_summary=message,
        output_json={"status": code_normalization["status"], "enabled": code_normalization["enabled"]},
    )
current_step = None
```

- [ ] **Step 6: Run environment validation after normalization**

Keep existing environment validation code, but it must now receive the possibly updated:

```python
contract_validation["normalized_payload"]
```

- [ ] **Step 7: Move draft generation after environment validation**

After environment validation and before `safety_reviewer_agent`, add a dedicated trace step:

```python
current_step = start_workflow_step(
    run_id,
    "draft_generation",
    43,
    model=prompt_meta["model"],
    prompt_version=f"{prompt_meta['prompt_id']}:{prompt_meta['prompt_version']}",
    input_summary=f"validation_valid={ai_validation.get('valid')}",
)
draft_context = {
    "text": payload.text,
    "request_type": request_type,
    "fields": fields,
    "validation": validation,
    "contract": contract_block,
    "ai_validation": ai_validation,
    "code_normalization": code_normalization,
    "submission": metadata["submission"],
    "request": metadata["request"],
}
draft_messages = [
    intake_messages["draft_generator"][0],
    {"role": "user", "content": json.dumps(draft_context)},
]
draft_data = parse_json_response(
    await call_ollama_func(draft_messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
)
drafts = {
    "draft_wo_description": str(draft_data.get("draft_wo_description") or fields["summary"]),
    "internal_note": str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."),
    "client_reply": str(draft_data.get("client_reply") or "Thanks, we captured your request."),
}
finish_workflow_step(
    current_step,
    "passed",
    output_summary="Draft text generated after validation.",
    output_json={"draft_fields": sorted(drafts.keys())},
)
current_step = None
```

- [ ] **Step 8: Include `code_normalization` in final response**

Add this key to the final returned dict:

```python
"code_normalization": code_normalization,
```

- [ ] **Step 9: Run API tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer_intake_api
```

Expected: PASS.

---

## Task 8: Add Workflow Trace Assertions

**Files:**
- Modify: `tests/test_code_normalizer_intake_api.py`

- [ ] **Step 1: Add failing trace test**

Append:

```python
    def test_workflow_trace_records_code_normalizer_step_before_environment_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )
            trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")

        self.assertEqual(trace.status_code, 200, trace.text)
        steps = trace.json()["steps"]
        names = [step["step_name"] for step in steps]

        self.assertIn("code_normalization_suggestion_agent", names)
        self.assertLess(names.index("output_contract_validation"), names.index("code_normalization_suggestion_agent"))
        self.assertLess(names.index("code_normalization_suggestion_agent"), names.index("environment_validation"))
        self.assertLess(names.index("environment_validation"), names.index("draft_generation"))
```

- [ ] **Step 2: Run trace test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer_intake_api.CodeNormalizerIntakeApiTests.test_workflow_trace_records_code_normalizer_step_before_environment_validation
```

Expected: PASS after Task 7.

---

## Task 9: Add Test Console Panel

**Files:**
- Modify: `app/ui.py`
- Test: add to `tests/test_code_normalizer.py` or create `tests/test_code_normalizer_ui.py`

- [ ] **Step 1: Write failing UI source test**

Create `tests/test_code_normalizer_ui.py`:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CodeNormalizerUITests(unittest.TestCase):
    def test_test_console_renders_code_normalization_panel(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("Code Normalization", html)
        self.assertIn("function renderCodeNormalization", html)
        self.assertIn("renderCodeNormalization(data);", html)
        self.assertIn("tCodeNormalization", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run UI test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer_ui
```

Expected: FAIL because the panel does not exist.

- [ ] **Step 3: Add panel container to Test Console output**

In `app/ui.py`, find the Test Console result panels and add a container:

```html
<div class="ai-panel" id="tCodeNormalization">
  <div class="status-line"><h3>Code Normalization</h3><span class="pill">Not run</span></div>
  <p class="muted">Run CMMS Intake to see code normalization suggestions.</p>
</div>
```

- [ ] **Step 4: Add renderer**

Add this JavaScript function:

```javascript
function renderCodeNormalization(data) {
  const target = $("tCodeNormalization");
  if (!target) return;
  const block = data?.code_normalization;
  if (!block) {
    target.innerHTML = '<div class="status-line"><h3>Code Normalization</h3><span class="pill">Not available</span></div><p class="muted">No code normalization block returned.</p>';
    return;
  }
  const cls = block.status === "applied" ? "ok" : block.status === "failed" ? "danger" : block.status === "rejected" ? "warning" : "";
  const accepted = Object.entries(block.applied || {}).map(([field, value]) => `<li>${escapeHtml(field)} -> <strong>${escapeHtml(value)}</strong></li>`).join("");
  const rejected = (block.rejected || []).map(item => `<li>${escapeHtml(item.field || "unknown")} ${escapeHtml(item.suggested_code || "")}: ${escapeHtml(item.reason_code || item.reason || "rejected")}</li>`).join("");
  const suggestions = (block.suggestions || []).map(item => `<li>${escapeHtml(item.field)}: ${escapeHtml(item.input_value)} -> <strong>${escapeHtml(item.suggested_code)}</strong> (${item.confidence}) ${escapeHtml(item.reason || "")}</li>`).join("");
  target.innerHTML = `<div class="status-line"><h3>Code Normalization</h3><span class="pill ${cls}">${escapeHtml(block.status || "unknown")}</span></div>
    ${block.message ? `<p class="muted">${escapeHtml(block.message)}</p>` : ""}
    <h3>Accepted</h3><ul>${accepted || "<li>none</li>"}</ul>
    <h3>Suggestions</h3><ul>${suggestions || "<li>none</li>"}</ul>
    <h3>Rejected</h3><ul>${rejected || "<li>none</li>"}</ul>`;
}
```

- [ ] **Step 5: Call renderer after Test Console API response**

In the Test Console run handler, after `renderSafetyReviewer(data);`, add:

```javascript
renderCodeNormalization(data);
```

- [ ] **Step 6: Run UI test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer_ui
```

Expected: PASS.

---

## Task 10: Documentation

**Files:**
- Create: `docs/implementation/54-code-normalization-suggestion-agent-v1.md`

- [ ] **Step 1: Create implementation note**

Create `docs/implementation/54-code-normalization-suggestion-agent-v1.md`:

```markdown
# Code Normalization Suggestion Agent v1

## Purpose

Adds a bounded Code Normalization Suggestion Agent to the controlled `cmms-intake` workflow.

The agent proposes configured CMMS codes for supported fields when extracted values are ambiguous, multilingual, or invalid. Python remains responsible for deterministic acceptance or rejection.

## Supported Fields

- priority -> priorities
- work_order_type -> work_order_types
- job_type -> job_type
- assign_to -> assign_to
- issue_to -> issue_to_employee_number

## Workflow Position

Request -> Classifier -> Field Extractor -> Output Contract Validation -> Code Normalization Suggestion Agent -> Environment Validation -> Draft Generation -> Safety Reviewer Agent -> CMMS Auto-Push Gate -> Response Composition

## Safety Boundary

The agent cannot create work orders, approve requests, send email, write to CMMS, change code lists, change validation rules, bypass output contracts, bypass environment validation, or bypass Safety Reviewer and CMMS auto-push gates.

## Visibility

Accepted and rejected suggestions are returned in `code_normalization` and shown in the Test Console. Workflow trace records only counts, rejected reason codes, prompt id/version, model, and duration.

## Known Limits

Building and room normalization remain deterministic in v1. Per-environment thresholds are not configurable in v1.
```

---

## Task 11: Final Verification

**Files:**
- Verify all changed files

- [ ] **Step 1: Run compile checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\main.py app\ai_endpoints.py app\code_normalizer.py app\config.py app\models.py app\ui.py
.\.venv\Scripts\python.exe -m compileall app
```

Expected: exit code 0.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_code_normalizer tests.test_code_normalizer_intake_api tests.test_code_normalizer_ui
```

Expected: all tests pass.

- [ ] **Step 3: Run full regression suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 4: Check UI JavaScript syntax**

Run:

```powershell
@'
from pathlib import Path
import os
import subprocess
import sys
import tempfile

text = Path("app/ui.py").read_text(encoding="utf-8")
start = text.index("<script>") + len("<script>")
end = text.index("</script>", start)
js = text[start:end]
fd, path = tempfile.mkstemp(suffix=".js")
os.close(fd)
try:
    Path(path).write_text(js, encoding="utf-8")
    result = subprocess.run(["node", "--check", path], text=True, capture_output=True)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    raise SystemExit(result.returncode)
finally:
    try:
        os.remove(path)
    except OSError:
        pass
'@ | .\.venv\Scripts\python.exe -
```

Expected: exit code 0.

- [ ] **Step 5: Safety grep**

Run:

```powershell
rg "/chat|LLM judge|Router Agent|backend audio|send email|direct Ollama" app tests docs\implementation\54-code-normalization-suggestion-agent-v1.md
```

Expected: no new route or implementation that violates the guardrails. Existing documentation mentions are acceptable when they describe prohibited behavior.

- [ ] **Step 6: Manual smoke checklist**

Run the app locally and verify:

- `/ui` loads.
- Login works.
- Test Console `cmms-intake` works.
- Code Normalization panel appears.
- Prompt Versions lists `cmms-code-normalizer`.
- Workflow trace shows `code_normalization_suggestion_agent`.
- Safety Reviewer still appears after a successful intake.
- CMMS auto-push remains gated by contract, environment validation, reviewer status, and metadata readiness.

---

## Self-Review Checklist

- The plan starts with pure functions before pipeline wiring.
- The plan fixes `issue_to` mapping before normalizer support.
- The plan preserves raw extraction before inserting the normalizer.
- The plan seeds `cmms-code-normalizer` before pipeline use.
- The plan extends `IntakeResponse` before asserting API visibility.
- The plan moves draft generation after normalization and validation.
- The plan adds UI last.
- The plan includes compile, focused tests, full regression, UI JS check, and safety grep.
- The plan does not add Router Agent, autonomous planning, LLM judge, generic `/chat`, backend audio upload, new CMMS write-back route, or email sending.
