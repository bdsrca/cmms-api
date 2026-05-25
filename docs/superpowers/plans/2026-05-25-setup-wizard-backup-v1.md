# Setup Wizard And Backup V1 Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## File Structure

- `app/system_setup.py`: deterministic setup status checks, backup creation/listing, and restore preview helpers.
- `app/management_routes.py`: admin-only route bindings for setup status, backup creation/listing, and restore preview.
- `app/ui.py`: Setup Wizard admin navigation item, checklist rendering, backup buttons, and manifest download helper.
- `tests/test_setup_backup.py`: helper and route tests for setup status, backup safety, and non-admin denial.
- `tests/test_setup_wizard_ui.py`: static UI coverage for the new portal page and endpoint wiring.
- `docs/implementation/60-setup-wizard-and-backup.md`: purpose, checks, backup contents/exclusions, restore limitation, and verification notes.

## Task 1: Tests First

- [ ] Add helper tests that build an isolated SQLite DB, seed the minimum setup records, mock Ollama availability, and assert setup checks report expected statuses.
- [ ] Add backup tests that create a backup zip from the isolated DB and assert the archive contains only `manifest.json` plus the SQLite copy, with no `.env`, `api_keys.json`, logs, plaintext API key values, session cookies, or raw secret strings in the manifest.
- [ ] Add route tests proving a normal authenticated `user` role receives `403` from `/api/admin/setup/status`, `/api/admin/system/backup`, `/api/admin/system/backups`, and `/api/admin/system/restore-preview`.
- [ ] Add UI source tests for the `Setup Wizard` menu item, `setupWizard()` handler, status endpoint, backup endpoint, backup list endpoint, and manifest download button.
- [ ] Run the focused new tests and confirm they fail because the production code is not implemented yet.

## Task 2: Deterministic Helpers

- [ ] Implement `app/system_setup.py` with setup check rows using statuses `passed`, `warning`, `failed`, and `not_checked`.
- [ ] Check FastAPI running, DB file/schema, enabled admin, `LLM_API_KEY` presence, Ollama tags reachability, `qwen3:8b` availability, `DEFAULT` environment, enabled generated API key, required validation rule, active prompt versions, active output contract, logs directory writability, and backup directory writability.
- [ ] Implement safe zip backup creation in `data/backups`, using SQLite's backup API for the DB copy and a public-safe manifest with counts/booleans only.
- [ ] Implement backup listing by reading `manifest.json` from each backup zip.
- [ ] Implement restore preview only: inspect archive contents and manifest, return warnings, and perform no writes.

## Task 3: Admin APIs

- [ ] Add Pydantic restore-preview request model in `app/management_routes.py`.
- [ ] Register `GET /api/admin/setup/status`, `POST /api/admin/system/backup`, `GET /api/admin/system/backups`, and `POST /api/admin/system/restore-preview` with `current_admin`.
- [ ] Return helper output directly and keep local process-control API key requirements unchanged for existing process-control routes only.

## Task 4: Portal UI

- [ ] Add `setup` to the Admin navigation group.
- [ ] Add `setupWizard()` to fetch status and backups, render checklist rows with recommended actions, and show backup history.
- [ ] Add `refreshSetupStatus()`, `createSystemBackup()`, and `downloadLatestBackupManifest()` helpers.
- [ ] Keep secrets out of the UI by displaying statuses, counts, timestamps, and file names only.

## Task 5: Documentation And Verification

- [ ] Write `docs/implementation/60-setup-wizard-and-backup.md`.
- [ ] Run focused tests, py_compile, compileall, full unittest discovery, and `node --check` against the extracted UI script.
- [ ] Confirm no new LLM calls, no generic `/chat`, no autonomous planner, no unsafe CMMS write path, and no automatic email sending.
