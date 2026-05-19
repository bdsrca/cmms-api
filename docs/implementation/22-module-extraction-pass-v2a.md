# Module Extraction Pass v2A

## Purpose

This pass moves real helper implementations out of `app/main.py` while preserving the existing FastAPI routes, response shapes, database schema, prompts, validation behavior, and UI behavior.

The goal is maintainability, not feature growth.

## Modules Extracted

### `app/db.py`

`app/db.py` now owns shared runtime paths and SQLite connection helpers:

- `BASE_DIR`
- `DATA_DIR`
- `LOG_DIR`
- `DB_FILE`
- `LOG_FILE`
- `API_KEYS_JSON`
- `DB_LOCK`
- `db_connect`
- `db_execute`
- `db_fetchone`
- `db_fetchall`

`app/main.py` imports these helpers instead of defining them locally.

### `app/workflow_trace.py`

`app/workflow_trace.py` now owns workflow trace helper implementations:

- `start_workflow_run`
- `finish_workflow_run`
- `start_workflow_step`
- `finish_workflow_step`
- `fail_workflow_step`
- `get_workflow_run`
- `list_workflow_runs`
- `cleanup_workflow_runs`

The workflow trace routes remain in `app/main.py` for this pass and call the imported helpers.

### `app/regression_dashboard.py`

`app/regression_dashboard.py` now owns read-only dashboard aggregation helpers:

- `json_or_empty`
- `regression_required_suite_readiness`
- `regression_latest_suite_runs`
- `regression_recent_prompt_comparisons`
- `regression_recent_promotions`
- `regression_workflow_summary`
- `regression_top_failing_fields`
- `regression_recent_validation_failures`
- `build_regression_dashboard`

The `/api/admin/regression-dashboard` route remains in `app/main.py` and calls `build_regression_dashboard()`.

## Circular Import Strategy

The extracted modules do not import `app.main`.

- `app/workflow_trace.py` imports only from `app.db`.
- `app/regression_dashboard.py` imports only from `app.db`.
- `app/db.py` has no dependency on `app.main`.
- `app/main.py` imports the extracted helpers.

This keeps the dependency direction one-way for the extracted infrastructure and dashboard layers.

## Preserved Behavior

This pass intentionally does not change:

- API routes or HTTP methods
- API response shapes
- database tables or columns
- prompts
- output contract validation
- environment validation
- workflow trace behavior
- regression dashboard response shape
- auth and role enforcement
- UI behavior

The root `main.py` remains a compatibility wrapper, so `uvicorn main:app` continues to work.

## Remaining Monolith Areas

Large areas still live in `app/main.py` and can be extracted in later passes:

- auth and sessions
- API key management
- environment and code list management
- validation rules
- output contracts
- prompt versions
- test cases and replay
- test suites
- prompt comparisons and promotions
- AI endpoint orchestration
- UI HTML and JavaScript

## Validation

Run after this pass:

```powershell
python -m py_compile main.py app/main.py app/workflow_trace.py app/regression_dashboard.py app/db.py
python -m compileall app
```

Smoke checks should confirm:

- `/ui` loads
- admin login works
- normal users still receive `403` for admin endpoints
- `cmms-intake` still returns `run_id` and `trace`
- workflow run detail loads
- regression dashboard returns all expected sections
- prompt comparison, promotion gate, and test suite routes still work

Validation performed during this pass:

- `python -m py_compile main.py app/main.py app/workflow_trace.py app/regression_dashboard.py app/db.py`
- `python -m compileall app`
- TestClient smoke: 27 checks passed, 0 failed

## Safety Notes

No multi-agent logic, LLM judge, router agent, reviewer agent, code normalization agent, CMMS write-back, or email sending was added in this pass.
