# Connector Field Mapping And Dry Run Verification V1 Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## File Structure

- `app/db.py`: add nullable `field_mappings_json` column to `cmms_connectors`.
- `app/cmms_connectors.py`: normalize/store mappings, apply mapped fields to outgoing payload previews, and build deterministic dry-run verification output.
- `app/cmms_connector_routes.py`: accept mapping config and expose an admin-only dry-run verification route.
- `app/ui.py`: add connector mapping input and dry-run preview panel inside the existing environment connector UI.
- `tests/test_cmms_connector_mapping.py`: helper and route tests for mapping persistence, dry-run payload previews, and non-admin denial.
- `tests/test_cmms_connector_ui.py`: static UI coverage for mapping and dry-run controls.
- `docs/implementation/61-connector-field-mapping-and-dry-run.md`: purpose, behavior, safety boundary, and verification results.

## Task 1: Tests First

- [ ] Add a helper test that saves `field_mappings` on the connector and verifies public connector output includes mappings while secrets remain masked.
- [ ] Add a dry-run helper test that maps canonical fields such as `summary`, `priority`, and `asset_context.asset_id` into target CMMS field paths and returns `canonical_payload`, `mapped_payload`, `mapping_results`, `missing_required_fields`, and `unmapped_fields`.
- [ ] Add a route test for `POST /api/admin/environments/{environment_code}/cmms-connector/dry-run` that proves the response is a preview and no sender is called.
- [ ] Add a route test proving authenticated non-admin users receive `403` from the dry-run endpoint.
- [ ] Add UI source tests for the mapping textarea, dry-run sample textarea, dry-run button, and endpoint call.
- [ ] Run focused tests and confirm they fail because implementation is missing.

## Task 2: Mapping Helpers

- [ ] Add `field_mappings_json` to the connector schema and migrations.
- [ ] Implement mapping normalization that accepts a dict or list of `{source, target, required}` objects.
- [ ] Implement dotted-path value read/write helpers.
- [ ] Implement `apply_field_mappings(connector, payload)` that builds a mapped payload, records mapped/missing results, and lists unmapped top-level canonical fields.
- [ ] Update `connector_payload` so existing push/probe wrappers can use the mapped payload when mappings exist, while preserving current behavior when mappings are empty.

## Task 3: Dry-Run API

- [ ] Add route request model with `canonical_payload`.
- [ ] Add `dry_run_cmms_connector_mapping(environment_code, canonical_payload)` helper.
- [ ] Add `POST /api/admin/environments/{environment_code}/cmms-connector/dry-run` guarded by `current_admin`.
- [ ] Return endpoint URL, HTTP method, payload root key, mapped payload preview, and warnings only; never call the network sender.

## Task 4: UI

- [ ] Add a `Field mappings JSON` textarea to the existing connector form.
- [ ] Include mappings when saving connector settings.
- [ ] Render mappings when loading connector settings.
- [ ] Add dry-run sample JSON textarea, `Preview Mapped Payload` button, and preview output.
- [ ] Keep secrets masked and avoid displaying connector secret values.

## Task 5: Documentation And Verification

- [ ] Write `docs/implementation/61-connector-field-mapping-and-dry-run.md`.
- [ ] Run focused connector tests.
- [ ] Run `.\.venv\Scripts\python.exe -m py_compile main.py`.
- [ ] Run `.\.venv\Scripts\python.exe -m compileall app`.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest discover -s tests`.
- [ ] Extract `app/ui.py` script and run `node --check`.
- [ ] Confirm no new LLM calls, no generic `/chat`, no autonomous agent, no unsafe CMMS write, and no email sending.
