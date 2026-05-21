# Route Split v3C

## Purpose

Move Environment and Code Lists routes out of `app/main.py` into an `APIRouter` module with zero intended behavior change.

## Routes Moved

Moved from `app/main.py` to `app/environment_routes.py`:

- `GET /api/environments`
- `POST /api/admin/environments`
- `PATCH /api/admin/environments/{environment_code}`
- `GET /api/admin/environments/{environment_code}/codes`
- `POST /api/admin/environments/{environment_code}/codes/preview`
- `POST /api/admin/environments/{environment_code}/codes/import`
- `PATCH /api/admin/environments/{environment_code}/codes/{code_id}`

## Models Moved

- `EnvironmentRequest`
- `EnvironmentPatchRequest`
- `CodeImportRequest`
- `CodeValuePatchRequest`

## Modules Added

- `app/environment_routes.py`
  - Defines an `APIRouter`
  - Owns environment and code-list route registration
  - Delegates business behavior to `app.environments`
  - Keeps server-side session/admin guards with `current_user` and `current_admin`

## Main Wiring

`app/main.py` now imports and registers:

```python
from .environment_routes import router as environment_router

app.include_router(environment_router)
```

## Behavior Preserved

- Route paths are unchanged.
- HTTP methods are unchanged.
- Request model validation is unchanged.
- Environment list remains available to authenticated portal users.
- Environment create/update remains admin-only.
- Code-list read/import/preview/update remains admin-only.
- Code-list import preview, duplicate detection, metadata JSON validation, and update behavior remain in `app.environments`.

## Why This Route Group

Environment and code-list domain helpers were already extracted in v2G, so this route split moves only the HTTP layer and keeps business logic stable.

## Validation Results

- `python -m py_compile main.py app/main.py app/environment_routes.py app/environments.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/ui` load
  - admin login
  - authenticated environment list
  - admin environment create
  - admin environment patch
  - code import preview with duplicate detection
  - code import
  - code list read
  - code value patch with metadata JSON
  - normal user can list environments
  - normal user denied admin environment create
  - normal user denied admin code-list read
  - environment/code routes registered with expected methods
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Route Groups

Future route split passes can move:

- Validation and output contract routes
- Prompt/test-case/test-suite/regression routes
- AI endpoint routes
- System/process routes

Those should move one group at a time with targeted smoke tests.
