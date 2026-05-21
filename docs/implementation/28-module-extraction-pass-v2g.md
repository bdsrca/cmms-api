# Module Extraction Pass v2G

## Purpose

Move Environment and Code Lists helper logic out of `app/main.py` into `app/environments.py` with zero intended behavior change.

## Functions Moved

- Default environment seeding
- Code value import helpers
- CSV-style code parsing
- Code import preview
- Code list import
- Environment value loading
- Environment CRUD helper logic
- Code list read/update helper logic

## Modules Extracted

- `app/environments.py` now owns environment and code-list helper logic.
- `app/main.py` keeps the existing FastAPI routes and delegates to `app.environments`.
- `app/config.py` provides shared `ALLOWED_REQUEST_TYPES` and code category constants for extracted modules.

## Circular Import Strategy

`app/environments.py` imports only shared configuration, DB helpers, and validation-rule helpers. It does not import `app.main`.

Routes remain in `app/main.py`, which imports helper functions from `app.environments`.

## Behavior Preserved

- Existing environment routes are unchanged.
- Existing code-list routes are unchanged.
- Default environment seeding remains unchanged.
- Code import preview and import behavior remain unchanged.
- Code metadata JSON validation remains unchanged.
- Environment values still feed validation, prompt tests, and AI endpoint request resolution.

## Validation Results

- `python -m py_compile main.py app/main.py app/environments.py app/config.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/ui` load
  - admin login
  - environment create/update
  - code import preview/import/list/update
  - validation sample alias normalization
  - mocked `cmms-intake` with `run_id`, contract validation, and `ai_validation`
  - normal user denied admin environment access
  - saved test case run
  - test suite run
  - regression dashboard load
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Monolith Areas

- AI endpoint orchestration still lives in `app/main.py`.
- UI HTML and JavaScript still live in `app/main.py`.
- Database schema initialization still lives mostly in `app/main.py`.

Future passes can extract AI endpoint orchestration, UI/static assets, and schema initialization when the surrounding dependencies are ready.
