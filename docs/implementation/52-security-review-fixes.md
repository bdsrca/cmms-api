# Security Review Fixes

## Purpose

This pass addresses concrete issues found during project review while preserving the updated product decision that CMMS auto-push is allowed only through a controlled connector gate after review passes.

## Changes

- The portal no longer auto-fetches or displays the raw `LLM_API_KEY`.
- `/api/default-api-key` now returns an empty key value for compatibility instead of leaking the environment key.
- Connector secrets are protected before storage and are revealed only in memory when building outbound auth headers.
- Existing plaintext connector secrets are migrated to protected storage during startup.
- Local system controls now require local client access, an authenticated admin session, and `x-api-key` matching `LOCAL_CONTROL_API_KEY`.
- Auto-push now requires `review_passed=true` in addition to the existing contract, environment validation, handoff, metadata review, and human-review gates.

## Auto-Push Policy

Auto-push is not an autonomous agent action. It is a backend connector action gated by deterministic checks and safety review status.

The connector remains disabled unless an admin configures and enables it for an environment.

## Notes

The connector secret protection is intended for this local Windows-first project and prevents plaintext secrets from sitting directly in SQLite. A future production design should use a dedicated secret manager or OS-backed key protection policy.

`LLM_API_KEY` remains for AI endpoint calls only. Local process controls use `LOCAL_CONTROL_API_KEY` so API invocation and local machine control stay separated.

## Validation

Targeted security and connector tests were run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_security_review_fixes tests.test_cmms_auto_push tests.test_cmms_connector_config tests.test_cmms_connector_routes
```

Result: passed.

Full test discovery was also run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Result: 84 tests passed.
