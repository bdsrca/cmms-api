# Workflow Run Detail and Push Gate Dashboard

## Purpose

Improve operational visibility without adding new autonomous behavior. Operators can inspect a single workflow run in detail and see a lightweight CMMS push gate summary on the dashboard.

## Workflow Run Detail

- Logs now opens a Workflow Run Detail view instead of only a compact trace.
- The detail view shows:
  - run id, endpoint, environment, source, status, and duration
  - step timeline
  - contract validation
  - code normalization
  - environment validation
  - safety review
  - orchestration summary
  - CMMS push gate
- Existing actions remain available:
  - replay run
  - create test case
  - load metadata review and handoff candidate where available

## CMMS Push Gate Dashboard

- Regression dashboard data now includes `cmms_push_gate_summary`.
- The summary is built from existing `workflow_run_steps` records for the `cmms_auto_push` step.
- It reports:
  - push-ready count
  - blocked count
  - sent count
  - dry-run count
  - recent ready runs
  - recent blocked runs
  - top blocked reasons
  - recent push events

## Safety

- No new database table was added.
- No new LLM call was added.
- No generic chat endpoint was added.
- No autonomous router or LLM judge was added.
- CMMS write-back behavior was not changed.
- Email sending behavior was not changed.

## Verification

- Added UI tests for Workflow Run Detail panels.
- Added backend aggregation test for the CMMS push gate summary.
