# Canonical CMMS Payload Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a review-gated canonical CMMS work order payload preview to the existing CMMS handoff candidate response.

**Architecture:** Keep the current admin-only candidate endpoint as the only API entry point. Add a pure preview mapper in `app/intake_handoff.py`, attach the preview while building the existing candidate, and keep the trace UI unchanged because it already renders the candidate JSON.

**Tech Stack:** Python, FastAPI route tests via `unittest`, local workflow trace UI HTML/JavaScript.

---

## File Structure

- `tests/test_cmms_handoff_candidate.py`: extend candidate tests with canonical preview expectations and existing route/UI integration assertions.
- `app/intake_handoff.py`: add the pure canonical preview mapper and attach the mapped preview to reviewed candidates.
- `docs/superpowers/specs/2026-05-22-canonical-cmms-payload-preview-design.md`: design source for field mapping and safety boundaries.

### Task 1: Lock The Canonical Preview Contract

**Files:**
- Modify: `tests/test_cmms_handoff_candidate.py`

- [ ] **Step 1: Write the failing preview assertion**

Extend the existing reviewed candidate test so it expects the canonical payload
projection in the built candidate:

```python
self.assertEqual(
    candidate["cmms_payload_preview"],
    {
        "schema": "canonical_cmms_work_order_v1",
        "fields": {
            "summary": "Air conditioner is noisy.",
            "location": {"building": "ARC", "room": "205"},
            "priority": "NORMAL",
            "work_order_type": "HVAC",
            "assignment": {
                "assign_to": None,
                "issue_to": None,
                "job_type": None,
            },
            "requester": {
                "name": "Leon",
                "email": "bdsrca@gmail.com",
                "phone": "1234",
            },
            "requested_due_date": "2026-05-25",
            "source": {
                "method": "email",
                "submitted_at": "2026-05-22T14:30:00Z",
                "intake_run_id": "run_123",
            },
        },
    },
)
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
rtk proxy python -m unittest tests.test_cmms_handoff_candidate.CmmsHandoffCandidateTests.test_candidate_uses_reviewed_metadata_and_persisted_extraction_fields -q
```

Expected: fail because `cmms_payload_preview` is not present yet.

- [ ] **Step 3: Keep the existing gate assertion close to the preview contract**

Leave the existing admin/review gate test intact:

```python
self.assertIn("Metadata review must be applied", operations_source)
```

This keeps the preview coupled to the current reviewed-candidate API rather than
introducing a bypassing endpoint.

- [ ] **Step 4: Commit the red contract test**

```powershell
git add -- tests/test_cmms_handoff_candidate.py
git commit -m "test: cover canonical cmms payload preview"
```

### Task 2: Build The Canonical Mapping Projection

**Files:**
- Modify: `app/intake_handoff.py`
- Test: `tests/test_cmms_handoff_candidate.py`

- [ ] **Step 1: Add the pure mapping helper**

Add a helper next to the current handoff candidate builder:

```python
def build_canonical_cmms_payload_preview(payload: dict[str, Any], run_id: Any) -> dict[str, Any]:
    return {
        "schema": "canonical_cmms_work_order_v1",
        "fields": {
            "summary": payload.get("summary"),
            "location": {
                "building": payload.get("building"),
                "room": payload.get("room"),
            },
            "priority": payload.get("priority"),
            "work_order_type": payload.get("work_order_type"),
            "assignment": {
                "assign_to": payload.get("assign_to"),
                "issue_to": payload.get("issue_to"),
                "job_type": payload.get("job_type"),
            },
            "requester": {
                "name": payload.get("submitted_by"),
                "email": payload.get("submitted_email"),
                "phone": payload.get("submitted_phone"),
            },
            "requested_due_date": payload.get("requested_due"),
            "source": {
                "method": payload.get("submitted_method"),
                "submitted_at": payload.get("submitted_at"),
                "intake_run_id": run_id,
            },
        },
    }
```

- [ ] **Step 2: Reuse the candidate payload for the preview**

Build the existing candidate payload once and return it with the new preview:

```python
payload = {
    "summary": fields.get("summary"),
    "building": location.get("building") or fields.get("building"),
    "room": location.get("room") or fields.get("room"),
    "priority": fields.get("priority"),
    "work_order_type": extraction.get("request_type"),
    "assign_to": None,
    "issue_to": None,
    "job_type": None,
    "requested_due": request.get("requested_due"),
    "submitted_by": submission.get("submitted_by"),
    "submitted_email": submission.get("submitted_email"),
    "submitted_phone": submission.get("submitted_phone"),
    "submitted_at": submission.get("submitted_at"),
    "submitted_method": submission.get("submitted_method"),
}
```

Attach the new preview in the return block:

```python
"payload": payload,
"cmms_payload_preview": build_canonical_cmms_payload_preview(payload, run.get("run_id")),
```

- [ ] **Step 3: Run the focused candidate tests to verify GREEN**

Run:

```powershell
rtk proxy python -m unittest tests.test_cmms_handoff_candidate -q
```

Expected: candidate preview and existing gate/UI checks pass.

- [ ] **Step 4: Commit the mapper**

```powershell
git add -- app/intake_handoff.py tests/test_cmms_handoff_candidate.py
git commit -m "feat: preview canonical cmms payload"
```

### Task 3: Verify The Slice

**Files:**
- Verify: `app/intake_handoff.py`
- Verify: `app/operations_routes.py`
- Verify: `app/ui.py`
- Verify: `tests/test_cmms_handoff_candidate.py`

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
rtk proxy python -m unittest discover -s tests -q
```

Expected: all tests pass with no failures.

- [ ] **Step 2: Compile the touched Python and UI module**

Run:

```powershell
rtk proxy python -m py_compile app/intake_handoff.py app/operations_routes.py app/ui.py tests/test_cmms_handoff_candidate.py
```

Expected: command exits `0`.

- [ ] **Step 3: Inspect the diff scope**

Run:

```powershell
rtk proxy git diff -- app/intake_handoff.py tests/test_cmms_handoff_candidate.py
```

Expected: the code diff is limited to the canonical preview projection and its
test coverage.
