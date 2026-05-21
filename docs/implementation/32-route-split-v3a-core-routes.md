# Route Split v3A

## Purpose

Begin the APIRouter split with the lowest-risk core routes while preserving existing API behavior.

## Routes Moved

Moved from `app/main.py` to `app/core_routes.py`:

- `GET /health`
- `GET /ui`
- `GET /api/me`
- `GET /api/default-api-key`
- `GET /api/kb/status`

## Modules Added

- `app/core_routes.py`
  - Defines an `APIRouter`
  - Owns the low-risk core routes listed above
  - Imports only shared config, security helpers, and UI rendering

## Main Wiring

`app/main.py` now imports and registers:

```python
from .core_routes import router as core_router

app.include_router(core_router)
```

## Behavior Preserved

- Route paths are unchanged.
- HTTP methods are unchanged.
- Auth requirements are unchanged.
- `/ui` still returns the same portal HTML.
- `/health` response shape is unchanged.
- `/api/me` still uses the authenticated portal session.
- `/api/default-api-key` behavior is unchanged.
- `/api/kb/status` remains a placeholder.

## Why This Route Group First

These routes do not mutate database state and do not run AI workflows. Splitting them first proves router registration without risking admin write paths, prompt management, validation rules, or AI endpoint behavior.

## Validation Results

- `python -m py_compile main.py app/main.py app/core_routes.py app/config.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/health`
  - `/ui`
  - unauthenticated `/api/me` returns `401`
  - admin login
  - authenticated `/api/me`
  - `/api/default-api-key`
  - `/api/kb/status`
  - mocked `cmms-intake` still works
  - normal user still denied admin regression dashboard
  - moved routes are registered exactly once
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Route Groups

Future route split passes can move:

- Auth and user admin routes
- Environment/code-list routes
- Validation and output contract routes
- Prompt/test-case/test-suite/regression routes
- AI endpoint routes
- System/process routes

Those should move one group at a time with targeted smoke tests.
