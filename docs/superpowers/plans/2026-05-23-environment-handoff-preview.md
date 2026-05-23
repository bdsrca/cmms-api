# Environment Handoff Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `environment_handoff_preview` to reviewed CMMS handoff candidates when a workflow run has an `environment_code`.

**Architecture:** Keep the existing admin-only handoff candidate endpoint as the only API path. Add a pure environment preview builder in `app/intake_handoff.py` that flattens `cmms_payload_preview.fields`, calls existing environment validation, adds handoff-specific warnings for empty assignment fields, and attaches the result to the existing candidate response.

**Tech Stack:** Python, FastAPI route helpers, existing SQLite-backed environment code lists and validation rules, `unittest`.

---

## File Structure

- `tests/test_cmms_handoff_candidate.py`: extend candidate tests with environment preview expectations using injected fake environment/value validators for deterministic tests.
- `app/intake_handoff.py`: add environment preview mapping, validation normalization, status derivation, and candidate attachment.
- `docs/superpowers/specs/2026-05-22-environment-handoff-preview-design.md`: approved design source.

### Task 1: Lock Environment Preview Contract With Failing Tests

**Files:**
- Modify: `tests/test_cmms_handoff_candidate.py`

- [ ] **Step 1: Extend imports for the new helper**

Change the import block to:

```python
from app.intake_handoff import build_cmms_handoff_candidate, build_environment_handoff_preview
```

- [ ] **Step 2: Add a direct helper test for needs-review preview**

Add this test to `CmmsHandoffCandidateTests`:

```python
    def test_environment_preview_maps_canonical_payload_and_marks_needs_review(self) -> None:
        canonical_preview = {
            "schema": "canonical_cmms_work_order_v1",
            "fields": {
                "summary": "Air conditioner is too warm.",
                "location": {"building": "ARC", "room": "207"},
                "priority": "NORMAL",
                "work_order_type": "HVAC",
                "assignment": {"assign_to": None, "issue_to": None, "job_type": None},
                "requester": {
                    "name": "Leon",
                    "email": "leon@example.com",
                    "phone": "416-555-0199",
                },
                "requested_due_date": "2026-05-25",
                "source": {
                    "method": "email_api",
                    "submitted_at": "2026-05-22T12:00:00Z",
                    "intake_run_id": "run_20260522_120000_deadbeef",
                },
            },
        }

        def fake_get_environment_values(environment_code: str) -> dict[str, list[str]]:
            self.assertEqual(environment_code, "DEFAULT")
            return {"rooms": ["205"]}

        def fake_validate(environment_code: str, fields: dict[str, object]) -> dict[str, object]:
            self.assertEqual(environment_code, "DEFAULT")
            self.assertEqual(fields["room"], "207")
            return {
                "valid": True,
                "errors": [],
                "warnings": [
                    {
                        "field": "room",
                        "value": "207",
                        "message": "Room 207 is not in configured room codes.",
                    }
                ],
                "normalized": {
                    "building": "ARC",
                    "priority": "NORMAL",
                    "work_order_type": "HVAC",
                },
            }

        preview = build_environment_handoff_preview(
            canonical_preview,
            "DEFAULT",
            get_environment_values_func=fake_get_environment_values,
            validate_func=fake_validate,
        )

        self.assertEqual(preview["schema"], "environment_cmms_handoff_v1")
        self.assertEqual(preview["environment_code"], "DEFAULT")
        self.assertEqual(preview["status"], "needs_review")
        self.assertEqual(
            preview["fields"],
            {
                "summary": "Air conditioner is too warm.",
                "building": "ARC",
                "room": "207",
                "priority": "NORMAL",
                "work_order_type": "HVAC",
                "assign_to": None,
                "issue_to": None,
                "job_type": None,
                "requester_name": "Leon",
                "requester_email": "leon@example.com",
                "requester_phone": "416-555-0199",
                "requested_due_date": "2026-05-25",
                "source_method": "email_api",
                "intake_run_id": "run_20260522_120000_deadbeef",
            },
        )
        self.assertEqual(preview["validation"]["valid"], False)
        self.assertIn("Room 207 is not in configured room codes.", preview["validation"]["warnings"])
        self.assertIn("Assign To is empty.", preview["validation"]["warnings"])
        self.assertIn("Issue To is empty.", preview["validation"]["warnings"])
        self.assertIn("Job Type is empty.", preview["validation"]["warnings"])
        self.assertEqual(
            preview["validation"]["normalized"],
            {"building": "ARC", "priority": "NORMAL", "work_order_type": "HVAC"},
        )
```

- [ ] **Step 3: Add a direct helper test for blocked environment**

Add this test:

```python
    def test_environment_preview_blocks_invalid_environment(self) -> None:
        canonical_preview = {"schema": "canonical_cmms_work_order_v1", "fields": {"summary": "Test"}}

        def fake_get_environment_values(environment_code: str) -> dict[str, list[str]]:
            raise ValueError("Invalid or disabled environment_code")

        preview = build_environment_handoff_preview(
            canonical_preview,
            "MISSING",
            get_environment_values_func=fake_get_environment_values,
            validate_func=lambda environment_code, fields: {"valid": True, "errors": [], "warnings": [], "normalized": {}},
        )

        self.assertEqual(preview["schema"], "environment_cmms_handoff_v1")
        self.assertEqual(preview["environment_code"], "MISSING")
        self.assertEqual(preview["status"], "blocked")
        self.assertEqual(preview["validation"]["valid"], False)
        self.assertIn("Invalid or disabled environment_code", preview["validation"]["errors"])
```

- [ ] **Step 4: Add candidate attachment assertion**

In `test_candidate_uses_reviewed_metadata_and_persisted_extraction_fields`, after the existing `cmms_payload_preview` assertion, add:

```python
        self.assertEqual(candidate["environment_handoff_preview"]["schema"], "environment_cmms_handoff_v1")
        self.assertEqual(candidate["environment_handoff_preview"]["environment_code"], "DEFAULT")
        self.assertEqual(candidate["environment_handoff_preview"]["fields"]["requester_name"], "Leon")
        self.assertEqual(candidate["environment_handoff_preview"]["fields"]["requested_due_date"], "2026-05-25")
```

- [ ] **Step 5: Run the focused test to verify RED**

Run:

```powershell
rtk proxy python -m unittest tests.test_cmms_handoff_candidate -q
```

Expected: fail because `build_environment_handoff_preview` is not defined or `environment_handoff_preview` is not attached.

### Task 2: Implement Environment Preview Mapping

**Files:**
- Modify: `app/intake_handoff.py`
- Test: `tests/test_cmms_handoff_candidate.py`

- [ ] **Step 1: Import existing environment validation helpers**

Add imports below `from typing import Any`:

```python
from .environments import get_environment_values
from .validation_rules import validate_ai_output
```

- [ ] **Step 2: Add message and status helpers**

Add these helpers below `model_extraction_output`:

```python
def issue_messages(issues: Any) -> list[str]:
    messages: list[str] = []
    for issue in issues if isinstance(issues, list) else []:
        if isinstance(issue, dict):
            message = str(issue.get("message") or "").strip()
            if message:
                messages.append(message)
        else:
            message = str(issue).strip()
            if message:
                messages.append(message)
    return messages


def derive_environment_preview_status(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "blocked"
    if warnings:
        return "needs_review"
    return "ready"
```

- [ ] **Step 3: Add canonical flattening helper**

Add:

```python
def environment_handoff_fields(canonical_preview: dict[str, Any]) -> dict[str, Any]:
    fields = canonical_preview.get("fields") if isinstance(canonical_preview.get("fields"), dict) else {}
    location = fields.get("location") if isinstance(fields.get("location"), dict) else {}
    assignment = fields.get("assignment") if isinstance(fields.get("assignment"), dict) else {}
    requester = fields.get("requester") if isinstance(fields.get("requester"), dict) else {}
    source = fields.get("source") if isinstance(fields.get("source"), dict) else {}
    return {
        "summary": fields.get("summary"),
        "building": location.get("building"),
        "room": location.get("room"),
        "priority": fields.get("priority"),
        "work_order_type": fields.get("work_order_type"),
        "assign_to": assignment.get("assign_to"),
        "issue_to": assignment.get("issue_to"),
        "job_type": assignment.get("job_type"),
        "requester_name": requester.get("name"),
        "requester_email": requester.get("email"),
        "requester_phone": requester.get("phone"),
        "requested_due_date": fields.get("requested_due_date"),
        "source_method": source.get("method"),
        "intake_run_id": source.get("intake_run_id"),
    }
```

- [ ] **Step 4: Add assignment warning helper**

Add:

```python
def handoff_assignment_warnings(fields: dict[str, Any]) -> list[str]:
    warnings = []
    labels = {
        "assign_to": "Assign To",
        "issue_to": "Issue To",
        "job_type": "Job Type",
    }
    for field, label in labels.items():
        if not str(fields.get(field) or "").strip():
            warnings.append(f"{label} is empty.")
    return warnings
```

- [ ] **Step 5: Add environment preview builder**

Add:

```python
def build_environment_handoff_preview(
    canonical_preview: dict[str, Any],
    environment_code: Any,
    *,
    get_environment_values_func: Any = get_environment_values,
    validate_func: Any = validate_ai_output,
) -> dict[str, Any] | None:
    if not environment_code:
        return None
    env_code = str(environment_code).upper()
    fields = environment_handoff_fields(canonical_preview)
    base = {
        "schema": "environment_cmms_handoff_v1",
        "environment_code": env_code,
        "fields": fields,
    }
    if not isinstance(canonical_preview.get("fields"), dict):
        return {
            **base,
            "status": "blocked",
            "validation": {
                "valid": False,
                "missing_fields": [],
                "errors": ["Candidate lacks a usable canonical CMMS preview."],
                "warnings": [],
                "normalized": {},
            },
        }
    try:
        get_environment_values_func(env_code)
        validation = validate_func(env_code, fields)
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        message = str(detail or exc)
        return {
            **base,
            "status": "blocked",
            "validation": {
                "valid": False,
                "missing_fields": [],
                "errors": [message],
                "warnings": [],
                "normalized": {},
            },
        }

    errors = issue_messages(validation.get("errors"))
    warnings = issue_messages(validation.get("warnings")) + handoff_assignment_warnings(fields)
    missing_fields = [
        str(issue.get("field"))
        for issue in validation.get("errors", [])
        if isinstance(issue, dict) and not str(issue.get("value") or "").strip()
    ]
    status = derive_environment_preview_status(errors, warnings)
    return {
        **base,
        "status": status,
        "validation": {
            "valid": status == "ready",
            "missing_fields": missing_fields,
            "errors": errors,
            "warnings": warnings,
            "normalized": validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {},
        },
    }
```

- [ ] **Step 6: Attach the preview to candidates**

In `build_cmms_handoff_candidate`, build previews once:

```python
    cmms_payload_preview = build_canonical_cmms_payload_preview(payload, run.get("run_id"))
    environment_handoff_preview = build_environment_handoff_preview(cmms_payload_preview, run.get("environment_code"))
```

Then return:

```python
        "cmms_payload_preview": cmms_payload_preview,
        "environment_handoff_preview": environment_handoff_preview,
```

- [ ] **Step 7: Run focused tests to verify GREEN**

Run:

```powershell
rtk proxy python -m unittest tests.test_cmms_handoff_candidate -q
```

Expected: all candidate tests pass.

### Task 3: Verify Integration And Diff Scope

**Files:**
- Verify: `app/intake_handoff.py`
- Verify: `tests/test_cmms_handoff_candidate.py`

- [ ] **Step 1: Run focused compile check**

Run:

```powershell
rtk proxy python -m py_compile app/intake_handoff.py tests/test_cmms_handoff_candidate.py
```

Expected: command exits `0`.

- [ ] **Step 2: Run the available focused tests**

Run:

```powershell
rtk proxy python -m unittest tests.test_cmms_handoff_candidate tests.test_metadata_review_apply_api tests.test_intake_metadata_ui -q
```

Expected: focused tests pass.

- [ ] **Step 3: Run full test suite and record environment dependency result**

Run:

```powershell
rtk proxy python -m unittest discover -s tests -q
```

Expected: if the local Python environment has `fastapi` and `httpx`, all tests pass. If the environment is still missing those packages, record the exact `ModuleNotFoundError` output and do not claim full-suite success.

- [ ] **Step 4: Inspect diff scope**

Run:

```powershell
rtk proxy git diff -- app/intake_handoff.py tests/test_cmms_handoff_candidate.py
```

Expected: diff is limited to environment preview helper code and candidate test coverage.
