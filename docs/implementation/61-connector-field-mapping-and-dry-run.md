# Connector Field Mapping and Dry Run Verification v1

## Purpose

This pass adds deterministic CMMS connector field mapping and dry-run verification so an operator can preview how a canonical work-order payload will be transformed before any live CMMS write is possible.

The feature is configuration and preview only by default. It does not add new LLM calls, expose Ollama, add a generic chat endpoint, add autonomous planning, or send email.

## Backend Changes

- `cmms_connectors.field_mappings_json` stores public mapping rules.
- Connector configuration now accepts `field_mappings`.
- Public connector responses include mapping rules but continue to mask secrets.
- `POST /api/admin/environments/{environment_code}/cmms-connector/dry-run` returns a deterministic preview.

Mapping entries use:

```json
[
  { "source": "summary", "target": "description", "required": true },
  { "source": "priority", "target": "priorityCode", "required": true },
  { "source": "asset_context.asset_id", "target": "asset.id" }
]
```

The helper supports dotted source and target paths. Empty mappings preserve existing connector payload behavior.

## Dry Run Output

Dry-run verification returns:

- canonical payload
- mapped payload
- outgoing payload with `payload_root_key` applied when configured
- mapping result rows
- missing required source fields
- unmapped canonical top-level fields
- connector endpoint and method metadata
- warnings such as connector disabled or endpoint missing

The dry-run endpoint never calls the network sender and never records a CMMS push event.

## Probe and Push Behavior

Manual connector probe keeps its fixed probe payload even when field mappings are configured. This preserves probe behavior as a connectivity check.

When field mappings are configured, the controlled connector payload builder applies them for work-order payloads. Existing environments without mappings keep the prior payload shape.

## UI

The existing CMMS Connector tab now includes:

- `Field Mappings JSON`
- `Dry Run Sample JSON`
- `Preview Mapped Payload`

The preview result appears in the existing connector output panel. Secrets remain masked.

## Safety

- Admin-only portal session is required for mapping configuration and dry-run.
- API keys do not grant admin portal access.
- Dry-run does not call the sender.
- No CMMS write behavior is added outside the existing deterministic connector gate.
- No automatic email sending was added.
- No LLM judge, new LLM call, or autonomous planner was added.

## Verification

- Baseline connector tests before implementation: `20 tests OK`.
- Red tests failed before implementation due missing helper, endpoint, and UI controls.
- Focused connector mapping and connector regression tests passed.
- `.\.venv\Scripts\python.exe -m py_compile main.py` passed.
- `.\.venv\Scripts\python.exe -m compileall app` passed.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests` passed with 197 tests.
- Extracted `app/ui.py` script and ran `node --check`; passed.
