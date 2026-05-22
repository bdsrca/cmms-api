# Route Split v3G: Operations Routes

## Purpose

Move operational visibility routes out of `app/main.py` while preserving the current access rules and response shapes.

## Route Module

`app/operations_routes.py` now owns:

- Admin regression dashboard
- Admin process log read view
- Admin workflow run list and detail
- Usage report aggregation

It also owns the shared `LogResponse` model and `read_log_lines(...)` helper. `app/main.py` imports those for the remaining `/api/system/logs` process-control route so the log response shape stays shared.

## Preserved Behavior

- Existing paths and HTTP methods are unchanged.
- Regression dashboard and workflow trace list/detail remain admin-only.
- Admin log and usage report reads keep their existing authenticated-user access boundary.
- Usage report keeps the existing grouped query and `LIMIT 100`.
- Workflow test-case creation and replay stay in `app/test_routes.py`.
- Local system/process controls remain in `app/main.py` for a later bounded split.

## Validation

This pass should be verified with:

- `python -m py_compile main.py app/main.py app/operations_routes.py`
- `python -m compileall app`
- Targeted TestClient smoke checks for regression dashboard, admin logs, workflow run list/detail/404, usage report, normal-user access boundaries, and the remaining system logs route.

## Remaining Route Groups

Future route split passes can move:

- API key, settings, and local system/process routes
- Controlled AI endpoint routes
