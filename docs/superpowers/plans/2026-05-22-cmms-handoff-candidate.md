# CMMS Handoff Candidate Plan

## Scope

Generate a server-side CMMS work order candidate from reviewed metadata and the
persisted intake workflow extraction output. The endpoint remains admin-only and
must not write to CMMS.

## Files

- `tests/test_cmms_handoff_candidate.py`: cover candidate composition and route
  integration.
- `app/intake_handoff.py`: compose a candidate payload from workflow trace data
  plus a reviewed metadata record.
- `app/operations_routes.py`: expose the admin-only candidate endpoint and
  reject unreviewed or incomplete runs.
- `app/ui.py`: expose the candidate endpoint from workflow trace detail when a
  run has reviewed metadata.

## Tasks

1. Add failing tests for reviewed candidate composition and route/UI integration
   points.
2. Implement the candidate builder with advisory safety metadata and CMMS-facing
   payload fields.
3. Add the controlled admin route and a small workflow trace entry point for the
   candidate payload.
4. Run focused tests, the full test suite, and compile checks.
