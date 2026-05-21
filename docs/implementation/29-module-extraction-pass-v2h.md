# Module Extraction Pass v2H

## Purpose

Move controlled AI endpoint orchestration out of `app/main.py` into `app/ai_endpoints.py` with zero intended behavior change.

## Functions Moved

- Ollama chat call helper
- Model JSON parsing helper
- AI extraction normalization helpers
- Legacy extract-field validation helper
- Test endpoint execution helper used by saved test cases and suites
- `summarize-work-order` orchestration
- `cmms-assistant` orchestration
- `extract-work-order-fields` orchestration
- `cmms-intake` workflow orchestration

## Modules Extracted

- `app/ai_endpoints.py` now owns controlled AI endpoint helper logic.
- `app/main.py` keeps the public FastAPI routes and delegates to `app.ai_endpoints`.
- `app/main.py` still exposes a `call_ollama` wrapper for compatibility with existing smoke tests and monkeypatching.

## Callback Injection Strategy

Routes and test runners pass `app.main.call_ollama` into `app.ai_endpoints` helpers. This keeps existing monkeypatch behavior intact while avoiding any import from `app.ai_endpoints` back into `app.main`.

`execute_ai_endpoint_for_test` also receives `ExtractFieldsRequest` as an explicit request factory so test-case execution does not require `app.ai_endpoints` to import Pydantic route models from `app.main`.

## Circular Import Strategy

`app/ai_endpoints.py` imports only shared config, DB helpers, environment helpers, prompt helpers, validation helpers, output contract helpers, and workflow trace helpers.

It does not import `app.main`.

## Behavior Preserved

- Existing AI endpoint paths and HTTP methods are unchanged.
- API key enforcement remains in route dependencies.
- Prompt Version Manager integration remains unchanged.
- Workflow trace steps remain unchanged:
  - request received
  - model extraction
  - output contract validation
  - environment validation
  - response composed
- Output contract validation still runs before environment validation.
- Environment validation is still skipped when contract validation fails.
- Test case and suite execution still use the same AI endpoint pipeline.

## Validation Results

- `python -m py_compile main.py app/main.py app/ai_endpoints.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/ui` load
  - admin login
  - `summarize-work-order`
  - `cmms-assistant`
  - `extract-work-order-fields`
  - `cmms-intake` with workflow trace
  - workflow run detail
  - saved test case run
  - test suite run
  - regression dashboard
  - normal user denied admin workflow run access
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Monolith Areas

- UI HTML and JavaScript still live in `app/main.py`.
- Database schema initialization still mostly lives in `app/main.py`.
- FastAPI route registration still mostly lives in `app/main.py`.

Future passes can extract database schema/init, static UI assets, and APIRouter route modules.
