# Module Extraction Pass v2I

## Purpose

Move SQLite schema creation, index creation, and migration-safe column initialization out of `app/main.py` into `app/db.py` with zero intended behavior change.

## Functions Moved

- `init_db`
- `ensure_schema_columns`
- schema table creation statements
- schema index creation statements
- `code_values` migration-safe column checks

## Modules Extracted

- `app/db.py` now owns:
  - database paths
  - connection helpers
  - schema statements
  - index statements
  - schema initialization
  - migration-safe column initialization
- `app/main.py` now delegates startup initialization to `app.db.init_db`.

## Seed Callback Strategy

`app/db.py` does not import business modules. Instead, `init_db` accepts optional seed callbacks:

- `migrate_json_api_keys`
- `bootstrap_admin_user`
- `seed_default_environment`
- `seed_default_output_contracts`
- `seed_default_prompt_versions`

`app/main.py` supplies those callbacks during FastAPI startup. This keeps schema ownership in `app/db.py` without introducing circular imports.

## Behavior Preserved

- Existing SQLite tables are unchanged.
- Existing indexes are unchanged.
- Existing code-value migration behavior is unchanged.
- Startup still migrates legacy JSON API keys.
- Startup still bootstraps the admin user when env vars are present.
- Startup still seeds the default environment, output contracts, and prompt versions.

## Validation Results

- `python -m py_compile main.py app/main.py app/db.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - FastAPI startup with `app.db.init_db(seed_callbacks=...)`
  - default environment seed exists
  - active `cmms-intake` output contract exists
  - active `cmms-intake` prompt exists
  - workflow trace index exists
  - `/ui` load
  - admin login
  - environment list
  - mocked `cmms-intake` with trace, contract validation, and `ai_validation`
  - saved test case run
  - regression dashboard
  - normal user denied admin regression dashboard
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Monolith Areas

- UI HTML and JavaScript still live in `app/main.py`.
- FastAPI route registration still mostly lives in `app/main.py`.

Future passes can extract static UI assets and then split route groups into `APIRouter` modules.
