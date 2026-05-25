# Setup Wizard and Backup v1

## Purpose

Setup Wizard and Backup v1 adds an authenticated admin-only operator handoff page for local install readiness, backup creation, backup listing, and restore preview. The feature is deterministic: it does not call LLM generation, expose Ollama directly, add a chat endpoint, change CMMS push behavior, or send email.

## Admin APIs

- `GET /api/admin/setup/status`
- `POST /api/admin/system/backup`
- `GET /api/admin/system/backups`
- `POST /api/admin/system/restore-preview`

All four routes require an authenticated portal admin session through `current_admin`. API keys still do not grant admin portal access.

## Setup Checks

The status helper returns checklist rows with `passed`, `warning`, `failed`, or `not_checked` plus a recommended action for warning and failed items.

Checked items:

- Python/FastAPI app running
- SQLite DB initialized with required tables
- enabled admin user exists
- `LLM_API_KEY` configured, without returning its value
- Ollama tags endpoint reachable
- `qwen3:8b` present in Ollama tags when Ollama is reachable
- enabled `DEFAULT` environment exists
- at least one enabled generated API key exists
- at least one enabled required validation rule exists
- active prompt versions exist
- active output contract exists
- logs directory writable
- backup directory writable

## Backup Contents

Backups are zip files created under `data/backups`. Each archive contains only:

- `manifest.json`
- `portal.db`

The SQLite copy is made with SQLite's backup API. The manifest is public-safe configuration metadata: timestamps, counts, booleans, service/model names, archive contents, restore mode, and exclusions.

## Excluded Data

The backup archive does not include:

- `.env`
- `api_keys.json`
- logs
- raw API key plaintext
- raw secrets
- session cookies
- generated runtime temp files

The manifest records only secret presence/count metadata and does not include API key hashes or secret values.

## Restore Limitation

Restore is preview-only in v1. `POST /api/admin/system/restore-preview` inspects a selected backup archive, returns contents, manifest metadata, and warnings, and performs no filesystem or database writes.

## UI

The portal adds `Setup Wizard` under the Admin navigation group. The page shows checklist rows, recommended actions, backup history, and buttons for:

- Refresh Checks
- Create Backup
- Download Latest Backup Manifest

Secrets are not displayed in the UI.

## Verification

- Baseline before changes: `.\.venv\Scripts\python.exe -m unittest discover -s tests` passed with 184 tests.
- Focused red run: new setup/backup tests failed before implementation due missing helper/UI wiring.
- Focused green run: `.\.venv\Scripts\python.exe -m unittest tests.test_setup_backup tests.test_setup_wizard_ui` passed.
- `.\.venv\Scripts\python.exe -m py_compile main.py` passed.
- `.\.venv\Scripts\python.exe -m compileall app` passed.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests` passed with 190 tests.
- Extracted `app/ui.py` script and ran `node --check`; passed.
