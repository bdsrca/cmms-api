# CMMS API Connector Auto-Push Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest runnable CMMS REST connector framework with deterministic auto-push gates.

**Architecture:** Store one masked connector config per environment in SQLite, expose admin-only config endpoints, and add a pure gate/sender service with an injectable HTTP client. Wire the service into the controlled `cmms-intake` endpoint after canonical handoff preview creation.

**Tech Stack:** FastAPI, Pydantic, SQLite helper functions in `app/db.py`, `urllib.request` for simple HTTP POST, pytest/unittest style tests already used in the repo.

---

### Task 1: Connector Config Storage

**Files:**
- Modify: `app/db.py`
- Create: `app/cmms_connectors.py`
- Test: `tests/test_cmms_connector_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_cmms_connector_config.py` with tests for saving a connector, returning masked secrets, keeping an existing secret when the update omits it, and building auth headers.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_cmms_connector_config.py -q`

Expected: FAIL because `app.cmms_connectors` does not exist.

- [ ] **Step 3: Add DB table and connector helper module**

Add `cmms_connectors` table in `app/db.py`. Create `app/cmms_connectors.py` with `upsert_cmms_connector`, `get_cmms_connector`, `public_cmms_connector`, and `build_auth_headers`.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_cmms_connector_config.py -q`

Expected: PASS.

### Task 2: Auto-Push Gate and Sender

**Files:**
- Modify: `app/cmms_connectors.py`
- Test: `tests/test_cmms_auto_push.py`

- [ ] **Step 1: Write failing auto-push service tests**

Create tests for blocked states, HTTPS/localhost endpoint validation, auth header use, single fake POST when all gates pass, and sanitized failed responses.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_cmms_auto_push.py -q`

Expected: FAIL because the auto-push service functions do not exist.

- [ ] **Step 3: Implement minimal service functions**

Add `cmms_push_gate`, `send_cmms_payload`, and `auto_push_cmms_payload` to `app/cmms_connectors.py`. Keep all network work behind an injectable sender function.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_cmms_auto_push.py -q`

Expected: PASS.

### Task 3: Admin Connector API

**Files:**
- Create: `app/cmms_connector_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_cmms_connector_routes.py`

- [ ] **Step 1: Write failing route tests**

Create tests for admin-only `GET`, `PUT`, and config validation `POST /test` behavior, including masked secret responses.

- [ ] **Step 2: Run the route tests and verify RED**

Run: `python -m pytest tests/test_cmms_connector_routes.py -q`

Expected: FAIL because the routes are not registered.

- [ ] **Step 3: Add route module and include it**

Create `app/cmms_connector_routes.py` with Pydantic request models and admin dependencies. Include the router in `app/main.py`.

- [ ] **Step 4: Run the route tests and verify GREEN**

Run: `python -m pytest tests/test_cmms_connector_routes.py -q`

Expected: PASS.

### Task 4: Intake Integration

**Files:**
- Modify: `app/ai_endpoints.py`
- Modify: `app/intake_handoff.py`
- Test: `tests/test_cmms_intake_auto_push.py`

- [ ] **Step 1: Write failing intake integration tests**

Create tests that call the pure integration path with a fake sender and verify `cmms_push.status` is `sent` only when gates pass, otherwise `blocked`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_cmms_intake_auto_push.py -q`

Expected: FAIL because `cmms_push` is not attached to intake results.

- [ ] **Step 3: Wire auto-push into `cmms-intake`**

After canonical/environment handoff preview is available, call `auto_push_cmms_payload` and include a `cmms_push` block in the response and workflow step output.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_cmms_intake_auto_push.py -q`

Expected: PASS.

### Task 5: Minimal UI and Regression Check

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_showcase.py` or nearest UI snapshot/smoke test

- [ ] **Step 1: Add basic admin UI controls**

Add a compact connector panel for endpoint, auth type, header name, secret replacement, enabled, and auto-push enabled. Show masked secret status and latest `cmms_push` block in candidate output.

- [ ] **Step 2: Run targeted regression tests**

Run:

```powershell
python -m pytest tests/test_cmms_connector_config.py tests/test_cmms_auto_push.py tests/test_cmms_connector_routes.py tests/test_cmms_intake_auto_push.py tests/test_cmms_handoff_candidate.py -q
```

Expected: PASS.

- [ ] **Step 3: Run broader verification**

Run: `python -m pytest -q`

Expected: PASS or report existing unrelated failures clearly.
