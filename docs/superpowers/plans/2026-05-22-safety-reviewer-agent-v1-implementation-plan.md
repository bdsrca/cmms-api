# Safety Reviewer Agent v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded Safety Reviewer Agent step to `cmms-intake` that reviews contract-valid results without changing deterministic validation gates.

**Architecture:** The reviewer is a workflow step inside `app/ai_endpoints.py`, backed by a small helper module for reviewer context, prompt calls, and output normalization. It uses the existing prompt version system with a new endpoint key `cmms-intake-reviewer`, records its own workflow trace step, and adds an advisory `review` block to the existing intake response.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite, existing prompt manager, existing workflow trace helpers, browser UI source tests.

---

## Files

- Create: `app/safety_reviewer.py`
- Modify: `app/config.py`
- Modify: `app/ai_endpoints.py`
- Modify: `app/models.py`
- Modify: `app/ui.py`
- Create: `tests/test_safety_reviewer.py`
- Create: `tests/test_safety_reviewer_intake_api.py`
- Create: `tests/test_safety_reviewer_ui.py`
- Create: `docs/implementation/45-safety-reviewer-agent-v1.md`

Do not change public route paths. Do not add `/chat`. Do not add CMMS write-back, work order creation, email sending, router agents, autonomous planning, or LLM judge behavior.

---

### Task 1: Reviewer Output Normalization Helper

**Files:**
- Create: `app/safety_reviewer.py`
- Create: `tests/test_safety_reviewer.py`

- [ ] **Step 1: Write failing normalization tests**

Create `tests/test_safety_reviewer.py` with:

```python
import unittest

from app.safety_reviewer import (
    failed_reviewer_block,
    normalize_reviewer_output,
    skipped_reviewer_block,
)


class SafetyReviewerTests(unittest.TestCase):
    def test_normalize_reviewer_output_accepts_valid_review(self) -> None:
        review = normalize_reviewer_output(
            {
                "status": "pass",
                "human_review_recommended": True,
                "risk_flags": [" Missing info ", "Missing info", ""],
                "notes": ["Review the client reply."],
            }
        )

        self.assertEqual(
            review,
            {
                "enabled": True,
                "status": "pass",
                "human_review_recommended": True,
                "risk_flags": ["Missing info"],
                "notes": ["Review the client reply."],
                "source": "safety_reviewer_agent",
            },
        )

    def test_normalize_reviewer_output_downgrades_unknown_status_to_warning(self) -> None:
        review = normalize_reviewer_output(
            {
                "status": "needs-work",
                "human_review_recommended": "yes",
                "risk_flags": "not-a-list",
                "notes": "not-a-list",
            }
        )

        self.assertEqual(review["status"], "warning")
        self.assertFalse(review["human_review_recommended"])
        self.assertEqual(review["risk_flags"], [])
        self.assertEqual(review["notes"], [])

    def test_normalize_reviewer_output_caps_lists_and_strings(self) -> None:
        review = normalize_reviewer_output(
            {
                "status": "warning",
                "human_review_recommended": False,
                "risk_flags": [f"flag-{index}" for index in range(20)],
                "notes": ["x" * 500],
            }
        )

        self.assertLessEqual(len(review["risk_flags"]), 8)
        self.assertLessEqual(len(review["notes"][0]), 240)

    def test_skipped_reviewer_block_is_advisory_and_disabled(self) -> None:
        review = skipped_reviewer_block("Skipped because output contract validation failed.")

        self.assertEqual(review["enabled"], False)
        self.assertEqual(review["status"], "skipped")
        self.assertFalse(review["human_review_recommended"])
        self.assertEqual(review["message"], "Skipped because output contract validation failed.")

    def test_failed_reviewer_block_does_not_recommend_human_review_by_side_effect(self) -> None:
        review = failed_reviewer_block("Model returned invalid JSON")

        self.assertEqual(review["enabled"], True)
        self.assertEqual(review["status"], "fail")
        self.assertFalse(review["human_review_recommended"])
        self.assertIn("Model returned invalid JSON", review["notes"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: fail with `ModuleNotFoundError: No module named 'app.safety_reviewer'`.

- [ ] **Step 3: Implement the helper**

Create `app/safety_reviewer.py` with:

```python
"""Safety reviewer agent helpers for controlled CMMS intake workflows."""

from typing import Any

REVIEW_SOURCE = "safety_reviewer_agent"
ALLOWED_REVIEW_STATUSES = {"pass", "warning", "fail"}
MAX_REVIEW_ITEMS = 8
MAX_REVIEW_TEXT_LENGTH = 240


def clean_review_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip()
    if not text:
        return None
    if len(text) > MAX_REVIEW_TEXT_LENGTH:
        return text[: MAX_REVIEW_TEXT_LENGTH - 3] + "..."
    return text


def normalize_reviewer_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_review_text(item)
        if text and text not in seen:
            normalized.append(text)
            seen.add(text)
        if len(normalized) >= MAX_REVIEW_ITEMS:
            break
    return normalized


def normalize_reviewer_status(value: Any) -> str:
    status = value.strip().lower() if isinstance(value, str) else ""
    return status if status in ALLOWED_REVIEW_STATUSES else "warning"


def normalize_reviewer_output(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": True,
        "status": normalize_reviewer_status(data.get("status")),
        "human_review_recommended": data.get("human_review_recommended") if isinstance(data.get("human_review_recommended"), bool) else False,
        "risk_flags": normalize_reviewer_list(data.get("risk_flags")),
        "notes": normalize_reviewer_list(data.get("notes")),
        "source": REVIEW_SOURCE,
    }


def skipped_reviewer_block(message: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "skipped",
        "human_review_recommended": False,
        "risk_flags": [],
        "notes": [],
        "source": REVIEW_SOURCE,
        "message": message,
    }


def failed_reviewer_block(message: str) -> dict[str, Any]:
    note = clean_review_text(message) or "Safety reviewer failed."
    return {
        "enabled": True,
        "status": "fail",
        "human_review_recommended": False,
        "risk_flags": ["reviewer_failed"],
        "notes": [note],
        "source": REVIEW_SOURCE,
    }
```

- [ ] **Step 4: Run the test to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: `Ran 5 tests` and `OK`.

---

### Task 2: Reviewer Prompt Endpoint Seeding

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_safety_reviewer.py`

- [ ] **Step 1: Add failing prompt endpoint tests**

Append to `tests/test_safety_reviewer.py`:

```python
from app.config import DEFAULT_PROMPT_VERSIONS, SUPPORTED_PROMPT_ENDPOINTS


class SafetyReviewerPromptConfigTests(unittest.TestCase):
    def test_reviewer_prompt_endpoint_is_supported_and_seeded(self) -> None:
        self.assertIn("cmms-intake-reviewer", SUPPORTED_PROMPT_ENDPOINTS)
        prompt = DEFAULT_PROMPT_VERSIONS["cmms-intake-reviewer"]
        self.assertEqual(prompt["version"], "v1")
        self.assertIn("/no_think", prompt["system_prompt"])
        self.assertIn("Return JSON only", prompt["system_prompt"])
        self.assertIn("Do not change extracted fields", prompt["system_prompt"])
        self.assertEqual(prompt["user_template"], "{{context_json}}")
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: fail because `"cmms-intake-reviewer"` is not supported or seeded.

- [ ] **Step 3: Add the reviewer endpoint to config**

In `app/config.py`, update `SUPPORTED_PROMPT_ENDPOINTS`:

```python
SUPPORTED_PROMPT_ENDPOINTS = {
    "cmms-intake",
    "cmms-intake-reviewer",
    "summarize-work-order",
    "extract-work-order-fields",
    "cmms-assistant",
}
```

Add a new `DEFAULT_PROMPT_VERSIONS` entry:

```python
"cmms-intake-reviewer": {
    "version": "v1",
    "name": "Default safety reviewer prompt",
    "temperature": 0.1,
    "system_prompt": (
        "/no_think\n"
        "You are a Safety Reviewer Agent for a controlled CMMS intake workflow. "
        "Return JSON only with this shape: "
        "{\"status\":\"pass\",\"human_review_recommended\":false,\"risk_flags\":[],\"notes\":[]}. "
        "Allowed status values are pass, warning, and fail. "
        "Review for advisory safety risk, missing information, contradictions, unsafe promises, "
        "or over-confident draft language. "
        "Do not change extracted fields, normalized codes, validation results, drafts, or response shape. "
        "Do not claim that a work order was created. Do not approve, dispatch, write to CMMS, or send email. "
        "Keep risk_flags and notes concise."
    ),
    "user_template": "{{context_json}}",
},
```

- [ ] **Step 4: Run the test to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: all tests pass.

---

### Task 3: Reviewer Context Builder And Prompt Call

**Files:**
- Modify: `app/safety_reviewer.py`
- Test: `tests/test_safety_reviewer.py`

- [ ] **Step 1: Add failing context and call tests**

Append:

```python
import json


class SafetyReviewerCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_safety_reviewer_agent_uses_prompt_context_and_normalizes_output(self) -> None:
        calls = []

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            calls.append({"messages": messages, "temperature": temperature, "model": model})
            return json.dumps(
                {
                    "status": "warning",
                    "human_review_recommended": True,
                    "risk_flags": ["Unsafe promise"],
                    "notes": ["Client reply sounds too certain."],
                }
            )

        from app.safety_reviewer import run_safety_reviewer_agent

        review, prompt_meta = await run_safety_reviewer_agent(
            result={"summary": "AC is noisy.", "building": "ARC"},
            contract={"valid": True, "errors": [], "warnings": [], "version": "v1"},
            ai_validation={"valid": True, "errors": [], "warnings": [], "normalized": {}},
            drafts={"client_reply": "We will dispatch someone now."},
            call_ollama_func=fake_call_ollama,
        )

        self.assertEqual(review["status"], "warning")
        self.assertTrue(review["human_review_recommended"])
        self.assertEqual(review["risk_flags"], ["Unsafe promise"])
        self.assertEqual(prompt_meta["endpoint"], "cmms-intake-reviewer")
        self.assertEqual(len(calls), 1)
        self.assertIn("AC is noisy.", calls[0]["messages"][1]["content"])

    async def test_run_safety_reviewer_agent_invalid_json_returns_failed_block(self) -> None:
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            return "not json"

        from app.safety_reviewer import run_safety_reviewer_agent

        review, _prompt_meta = await run_safety_reviewer_agent(
            result={"summary": "AC is noisy."},
            contract={"valid": True, "errors": [], "warnings": [], "version": "v1"},
            ai_validation={"valid": True, "errors": [], "warnings": [], "normalized": {}},
            drafts={},
            call_ollama_func=fake_call_ollama,
        )

        self.assertEqual(review["status"], "fail")
        self.assertEqual(review["source"], "safety_reviewer_agent")
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: fail because `run_safety_reviewer_agent` does not exist.

- [ ] **Step 3: Implement reviewer context and call helper**

In `app/safety_reviewer.py`, add:

```python
import json
from collections.abc import Awaitable, Callable

from .prompts import prompt_messages

ReviewerCaller = Callable[..., Awaitable[str]]


def reviewer_context_json(
    *,
    result: dict[str, Any],
    contract: dict[str, Any],
    ai_validation: dict[str, Any],
    drafts: dict[str, Any],
) -> str:
    context = {
        "advisory_mode": {
            "cmms_write_back": False,
            "work_order_created": False,
            "email_sent": False,
            "reviewer_can_modify_fields": False,
        },
        "result": result,
        "contract": contract,
        "environment_validation": ai_validation,
        "drafts": drafts,
    }
    return json.dumps(context, ensure_ascii=True, default=str)


async def run_safety_reviewer_agent(
    *,
    result: dict[str, Any],
    contract: dict[str, Any],
    ai_validation: dict[str, Any],
    drafts: dict[str, Any],
    call_ollama_func: ReviewerCaller,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context_json = reviewer_context_json(
        result=result,
        contract=contract,
        ai_validation=ai_validation,
        drafts=drafts,
    )
    messages, prompt_meta = prompt_messages("cmms-intake-reviewer", {"context_json": context_json})
    try:
        content = await call_ollama_func(
            messages,
            temperature=prompt_meta["temperature"],
            model=prompt_meta["model"],
        )
        parsed = json.loads(content.strip())
        if not isinstance(parsed, dict):
            return failed_reviewer_block("Safety reviewer returned invalid JSON"), prompt_meta
        return normalize_reviewer_output(parsed), prompt_meta
    except json.JSONDecodeError:
        return failed_reviewer_block("Safety reviewer returned invalid JSON"), prompt_meta
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: all tests pass.

---

### Task 4: API Response Model Includes Review Block

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_safety_reviewer.py`

- [ ] **Step 1: Add failing response model test**

Append:

```python
from app.models import IntakeResponse


class SafetyReviewerResponseModelTests(unittest.TestCase):
    def test_intake_response_allows_review_block(self) -> None:
        response = IntakeResponse(
            model="qwen3:8b",
            review={
                "enabled": True,
                "status": "pass",
                "human_review_recommended": False,
                "risk_flags": [],
                "notes": [],
                "source": "safety_reviewer_agent",
            },
        )

        self.assertEqual(response.review["status"], "pass")
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: fail because `IntakeResponse` has no `review` field or because the response model drops the field.

- [ ] **Step 3: Add `review` to `IntakeResponse`**

In `app/models.py`, add this field near `ai_validation`:

```python
    review: dict[str, Any] | None = None
```

- [ ] **Step 4: Run the test to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer
```

Expected: all tests pass.

---

### Task 5: Integrate Reviewer Into `cmms-intake`

**Files:**
- Modify: `app/ai_endpoints.py`
- Create: `tests/test_safety_reviewer_intake_api.py`

- [ ] **Step 1: Write failing API tests for run, skip, invalid JSON, and validation isolation**

Create `tests/test_safety_reviewer_intake_api.py`:

```python
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_main


def fake_payload() -> dict:
    return {
        "text": "The air conditioner in ARC room 205 is noisy.",
        "valid_buildings": ["ARC"],
        "valid_priorities": ["NORMAL"],
    }


class SafetyReviewerIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "safety-reviewer-test-key"

    def test_contract_passed_runs_reviewer_and_adds_trace_step(self) -> None:
        async def fake_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.91})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "NORMAL",
                        "summary": "Air conditioner in ARC room 205 is noisy.",
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps(
                    {
                        "draft_wo_description": "Check ARC room 205 air conditioner.",
                        "internal_note": "Advisory draft only.",
                        "client_reply": "Thanks, we captured the request.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps(
                    {
                        "status": "pass",
                        "human_review_recommended": False,
                        "risk_flags": [],
                        "notes": [],
                    }
                )
            raise AssertionError(system)

        app_main.ai_call_ollama = fake_ollama

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "safety-reviewer-test-key"},
                json=fake_payload(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["review"]["status"], "pass")
        self.assertEqual(data["review"]["source"], "safety_reviewer_agent")

        with TestClient(app_main.app) as client:
            trace = client.get(
                f"/api/admin/workflow-runs/{data['run_id']}",
                cookies=self._admin_cookie(client),
            )
        self.assertIn("safety_reviewer_agent", trace.text)

    def test_reviewer_warning_does_not_change_deterministic_validation(self) -> None:
        async def fake_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.91})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "NORMAL",
                        "summary": "Air conditioner in ARC room 205 is noisy.",
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps({"draft_wo_description": "x", "internal_note": "x", "client_reply": "x"})
            if "Safety Reviewer Agent" in system:
                return json.dumps(
                    {
                        "status": "warning",
                        "human_review_recommended": True,
                        "risk_flags": ["review draft"],
                        "notes": ["Client reply may be too terse."],
                    }
                )
            raise AssertionError(system)

        app_main.ai_call_ollama = fake_ollama

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "safety-reviewer-test-key"},
                json=fake_payload(),
            )

        data = response.json()
        self.assertEqual(data["review"]["status"], "warning")
        self.assertEqual(data["validation"]["needs_human_review"], False)

    def test_reviewer_invalid_json_returns_safe_failure_block(self) -> None:
        async def fake_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.91})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "NORMAL",
                        "summary": "Air conditioner in ARC room 205 is noisy.",
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps({"draft_wo_description": "x", "internal_note": "x", "client_reply": "x"})
            if "Safety Reviewer Agent" in system:
                return "not json"
            raise AssertionError(system)

        app_main.ai_call_ollama = fake_ollama

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "safety-reviewer-test-key"},
                json=fake_payload(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["review"]["status"], "fail")

    def test_contract_failure_skips_reviewer(self) -> None:
        async def fake_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.91})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "NORMAL",
                        "summary": "Air conditioner in ARC room 205 is noisy.",
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps({"draft_wo_description": "x", "internal_note": "x", "client_reply": "x"})
            if "Safety Reviewer Agent" in system:
                raise AssertionError("reviewer should not run")
            raise AssertionError(system)

        app_main.ai_call_ollama = fake_ollama

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
                    headers={"x-api-key": "safety-reviewer-test-key"},
                    json=fake_payload(),
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["review"]["status"], "skipped")

    def _admin_cookie(self, client: TestClient) -> dict[str, str]:
        os.environ["ADMIN_USERNAME"] = "reviewer-admin"
        os.environ["ADMIN_PASSWORD"] = "reviewer-admin-password"
        login = client.post(
            "/api/auth/login",
            json={"username": "reviewer-admin", "password": "reviewer-admin-password"},
        )
        if login.status_code != 200:
            self.skipTest("admin bootstrap not available in this smoke context")
        return dict(client.cookies)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_intake_api
```

Expected: fail because `review` and `safety_reviewer_agent` are not integrated.

- [ ] **Step 3: Integrate reviewer imports**

In `app/ai_endpoints.py`, add imports:

```python
from .safety_reviewer import (
    run_safety_reviewer_agent,
    skipped_reviewer_block,
)
```

- [ ] **Step 4: Add reviewer step after environment validation and before response composition**

In `cmms_intake`, after the environment validation block and before `response_composed`, add:

```python
        current_step = start_workflow_step(
            run_id,
            "safety_reviewer_agent",
            45,
            input_summary=f"contract_valid={contract_validation['valid']}",
        )
        if contract_validation["valid"]:
            review, reviewer_prompt_meta = await run_safety_reviewer_agent(
                result=contract_validation["normalized_payload"],
                contract=contract_block,
                ai_validation=ai_validation,
                drafts={
                    "draft_wo_description": str(draft_data.get("draft_wo_description") or fields["summary"]),
                    "internal_note": str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."),
                    "client_reply": str(draft_data.get("client_reply") or "Thanks, we captured your request."),
                },
                call_ollama_func=call_ollama_func,
            )
            db_execute(
                "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
                (
                    reviewer_prompt_meta["model"],
                    f"{reviewer_prompt_meta['prompt_id']}:{reviewer_prompt_meta['prompt_version']}",
                    current_step,
                ),
            )
            reviewer_status = "failed" if review["status"] == "fail" else ("warning" if review["status"] == "warning" else "passed")
            finish_workflow_step(
                current_step,
                reviewer_status,
                output_summary=f"review_status={review['status']} flags={len(review['risk_flags'])} notes={len(review['notes'])}",
                output_json={
                    "status": review["status"],
                    "human_review_recommended": review["human_review_recommended"],
                    "risk_flag_count": len(review["risk_flags"]),
                    "note_count": len(review["notes"]),
                    "prompt_id": reviewer_prompt_meta["prompt_id"],
                    "prompt_version": reviewer_prompt_meta["prompt_version"],
                },
            )
        else:
            review = skipped_reviewer_block("Skipped because output contract validation failed.")
            finish_workflow_step(
                current_step,
                "skipped",
                output_summary=review["message"],
                output_json={"status": review["status"], "enabled": review["enabled"]},
            )
        current_step = None
```

Then add `"review": review` to the returned response dictionary.

Keep existing `validation`, `ai_validation`, `fields`, and `result` assignments unchanged.

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer tests.test_safety_reviewer_intake_api
```

Expected: all tests pass.

---

### Task 6: Test Console Safety Reviewer Panel

**Files:**
- Modify: `app/ui.py`
- Create: `tests/test_safety_reviewer_ui.py`

- [ ] **Step 1: Write failing source-level UI tests**

Create `tests/test_safety_reviewer_ui.py`:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SafetyReviewerUITests(unittest.TestCase):
    def test_test_console_renders_safety_reviewer_panel(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("function renderSafetyReviewer", html)
        self.assertIn("Safety Reviewer", html)
        self.assertIn("human_review_recommended", html)
        self.assertIn("risk_flags", html)
        self.assertIn("renderSafetyReviewer(data);", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_ui
```

Expected: fail because the Safety Reviewer panel is not present.

- [ ] **Step 3: Add a renderer in `app/ui.py`**

Add a JavaScript function near existing validation/result renderers:

```javascript
function renderSafetyReviewer(data) {
  const target = document.getElementById("tReviewer");
  if (!target) return;
  const review = data?.review || {};
  if (!review.status) {
    target.innerHTML = `<div class="empty-state">No reviewer result yet.</div>`;
    return;
  }
  const flags = Array.isArray(review.risk_flags) ? review.risk_flags : [];
  const notes = Array.isArray(review.notes) ? review.notes : [];
  target.innerHTML = `
    <div class="result-section">
      <div class="section-heading">Safety Reviewer</div>
      <div class="kv-grid">
        <div><span>Status</span><strong>${escapeHtml(review.status)}</strong></div>
        <div><span>Human review recommended</span><strong>${review.human_review_recommended ? "Yes" : "No"}</strong></div>
      </div>
      ${review.message ? `<div class="notice">${escapeHtml(review.message)}</div>` : ""}
      <div class="mini-list"><span>Risk flags</span>${flags.length ? flags.map(flag => `<div>${escapeHtml(flag)}</div>`).join("") : `<em>None</em>`}</div>
      <div class="mini-list"><span>Notes</span>${notes.length ? notes.map(note => `<div>${escapeHtml(note)}</div>`).join("") : `<em>None</em>`}</div>
    </div>
  `;
}
```

Add a target container in the Test Console result area:

```html
<div id="tReviewer"></div>
```

Call it wherever the Test Console currently updates response panels:

```javascript
renderSafetyReviewer(data);
```

- [ ] **Step 4: Run the test to verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_ui
```

Expected: test passes.

---

### Task 7: Documentation And Compatibility Verification

**Files:**
- Create: `docs/implementation/45-safety-reviewer-agent-v1.md`

- [ ] **Step 1: Add implementation note**

Create `docs/implementation/45-safety-reviewer-agent-v1.md`:

```markdown
# Safety Reviewer Agent v1

## Purpose

Add a bounded Safety Reviewer Agent step to the controlled CMMS intake workflow.

## Behavior

The reviewer runs only after output contract validation passes. It reviews
normalized result data, deterministic validation blocks, and generated drafts
for advisory safety risk. It never modifies extracted fields, normalized codes,
validation results, drafts, or `needs_human_review`.

## Prompt Endpoint

The prompt endpoint is `cmms-intake-reviewer`, seeded through the existing
Prompt Version Manager.

## Trace

Workflow trace includes `safety_reviewer_agent` with passed, warning, failed, or
skipped status.

## Safety

No CMMS write-back, work order creation, email sending, router agent, autonomous
planning, LLM judge, backend audio route, or generic `/chat` route was added.

## Validation

Run:

- `python -m py_compile main.py app/main.py app/ai_endpoints.py app/safety_reviewer.py app/models.py app/config.py`
- `python -m compileall app`
- `python -m unittest tests.test_safety_reviewer tests.test_safety_reviewer_intake_api tests.test_safety_reviewer_ui`
- `python -m unittest discover -s tests`
```

- [ ] **Step 2: Run compile checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\main.py app\ai_endpoints.py app\safety_reviewer.py app\models.py app\config.py
```

Expected: exit code `0`.

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall app
```

Expected: exit code `0`.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer tests.test_safety_reviewer_intake_api tests.test_safety_reviewer_ui
```

Expected: all tests pass.

- [ ] **Step 4: Run full existing test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 5: Confirm prohibited routes/features were not added**

Run:

```powershell
rg -n '"/chat"|/chat|write_back|send_email|Router Agent|LLM judge' app tests docs
```

Expected:

- no `/chat` route;
- no CMMS write-back implementation;
- no email sending implementation;
- no LLM judge implementation.

Because the worktree is already dirty with many staged-era files, do not commit automatically unless the user explicitly asks for a commit.

---

## Self-Review Checklist

- [ ] Spec coverage: reviewer run/skip, output contract, prompt endpoint, trace, response block, UI, and tests are represented.
- [ ] Placeholder scan: no unfinished placeholder wording remains.
- [ ] Type consistency: `review`, `risk_flags`, `notes`, `human_review_recommended`, and `safety_reviewer_agent` are spelled consistently.
- [ ] Safety boundary: reviewer remains advisory only and cannot modify deterministic gates.
