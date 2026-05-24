# Orchestration Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic operator-facing orchestration summary for the end-to-end CMMS request workflow.

**Architecture:** Create a focused summary builder that reads existing workflow contexts and action-plan actions, then returns a stable `cmms_orchestration_summary_v1` object. Wire that object into `cmms-intake` before contract validation, refresh it after CMMS dry-run/final action statuses, and include it in draft context and API response.

**Tech Stack:** Python, FastAPI route helpers, SQLite-backed environment data, unittest.

---

### Task 1: Summary Builder

**Files:**
- Create: `app/orchestration_summary.py`
- Test: `tests/test_orchestration_summary.py`

- [ ] Write failing tests for a full AHU-3 plan showing work order, assignment, inventory shortage, procurement draft, dry-run action IDs, and an operator message.
- [ ] Run `python -m unittest tests.test_orchestration_summary` and expect import failure for `app.orchestration_summary`.
- [ ] Implement `build_orchestration_summary(...)` with no model calls and no external writes.
- [ ] Re-run the focused test and expect OK.

### Task 2: Intake Wiring

**Files:**
- Modify: `app/ai_endpoints.py`
- Modify: `app/config.py`
- Modify: `app/models.py`
- Modify: `app/output_contracts.py`
- Test: `tests/test_orchestration_summary_intake_api.py`
- Test: `tests/test_intake_metadata.py`

- [ ] Write failing intake tests proving `orchestration_summary` is returned, included in draft context, refreshed after dry-run push, and recorded in workflow trace.
- [ ] Run the intake tests and expect missing `orchestration_summary`.
- [ ] Add `orchestration_summary` to response model and default contract properties.
- [ ] Bump default `cmms-intake` output contract to `v7` with an inventory/procurement/orchestration name.
- [ ] Build an initial summary before output contract validation, then rebuild it after `finalize_action_plan`.
- [ ] Add an `orchestration_summary` workflow trace step after auto push.
- [ ] Re-run focused tests and expect OK.

### Task 3: Verification

**Files:**
- Existing tests only.

- [ ] Run `python -m py_compile app/orchestration_summary.py app/ai_endpoints.py app/config.py app/models.py app/output_contracts.py`.
- [ ] Run focused workflow tests covering asset, assignment, inventory, and orchestration.
- [ ] Run `python -m unittest discover -s tests`.
