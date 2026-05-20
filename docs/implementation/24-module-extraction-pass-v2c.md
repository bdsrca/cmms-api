# Module Extraction Pass v2C

## Purpose

This pass moves Saved Test Cases and Test Suites helper logic out of `app/main.py` with zero intended behavior change.

Routes remain in `app/main.py`; route handlers now call imported helpers from dedicated modules.

## Modules Extracted

### `app/test_cases.py`

`app/test_cases.py` now owns saved test case helper logic:

- test case listing, creation, update, delete, and detail serialization
- `compare_test_case_result`
- test case run status calculation
- single test case run persistence
- batch test case run helper
- test case run history helpers
- workflow-run create-test-case helper
- workflow-run replay helper

### `app/test_suites.py`

`app/test_suites.py` now owns test suite helper logic:

- test suite listing, creation, update, delete, and detail serialization
- suite membership add/remove helpers
- suite run helper
- batch suite run helper
- suite run history helpers
- suite summary and pass-rate calculation

## Callback Injection Strategy

The AI endpoint test runner still lives in `app/main.py` because it depends on the current prompt, Ollama, validation, and response model pipeline.

To avoid circular imports:

- `app/test_cases.py` accepts `endpoint_runner`, `prompt_row_for`, and `supported_prompt_endpoints` as explicit callback/context arguments.
- `app/test_suites.py` accepts `run_test_case_row`, `prompt_row_for`, `supported_prompt_endpoints`, and test-case runner kwargs.
- `app/main.py` provides small adapter functions for these callbacks.
- `app/prompt_comparisons.py` continues to receive a test-case runner callback.

## Circular Import Strategy

The extracted modules do not import `app.main`.

- `app/test_cases.py` imports only standard library helpers, FastAPI `HTTPException`, and `app.db`.
- `app/test_suites.py` imports only standard library helpers, FastAPI `HTTPException`, and `app.db`.
- `app/main.py` imports helpers from both modules.

## Preserved Behavior

This pass intentionally does not change:

- API routes or HTTP methods
- API response shapes
- database schema
- prompt text
- validation behavior
- UI behavior
- test case comparison behavior
- test case run persistence
- workflow replay safety behavior
- suite summary and pass-rate calculation
- suite membership behavior
- prompt comparison and promotion gate behavior
- admin-only authorization

## Validation

Completed after this pass:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app/main.py app/test_cases.py app/test_suites.py
.\.venv\Scripts\python.exe -m compileall app
```

Both commands passed.

Smoke checks completed with a deterministic fake Ollama response and FastAPI `TestClient`:

- `/ui` loads
- admin login works
- normal users still receive `403` for admin endpoints
- create/edit/run test case works
- batch test case run works
- mismatch detection works
- workflow replay works when stored input exists
- workflow replay fails safely when input is unavailable
- create/edit/delete suite works
- suite membership add/remove works
- suite run and pass-rate calculation work
- batch suite run works
- prompt comparison and promotion gate still work
- regression dashboard and cmms-intake still work
- no `/chat`, backend audio/upload/speech, CMMS write-back, or email routes were added

## Remaining Monolith Areas

Large areas still live in `app/main.py`:

- auth and sessions
- API key management
- environment and code list management
- validation rules
- output contracts
- prompt version CRUD
- AI endpoint orchestration
- UI HTML and JavaScript

## Safety Notes

No multi-agent logic, LLM judge, router agent, reviewer agent, code normalization agent, CMMS write-back, or email sending was added in this pass.
