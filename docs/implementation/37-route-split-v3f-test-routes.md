# Route Split v3F: Test Routes

## Purpose

Move Saved Test Case, Test Suite, and workflow replay/test-case creation routes out of `app/main.py` with zero intended API behavior change.

## Route Module

`app/test_routes.py` now owns:

- Saved test case CRUD, run, batch-run, and run-history routes
- Test suite CRUD, membership, run, batch-run, and run-history routes
- Workflow run `create-test-case` and `replay` routes
- Route-local Pydantic request models for test cases, suites, runs, and workflow run test-case creation

`app/main.py` keeps the endpoint execution callbacks that already connect test runs to controlled AI pipelines. It injects:

- `test_case_runner_kwargs`
- `test_suite_runner_kwargs`

The route module does not reverse-import `app.main`.

## Preserved Behavior

- Existing paths, methods, payload shapes, and admin-only guards remain unchanged.
- Test case and suite runs still call the existing helpers in `app/test_cases.py` and `app/test_suites.py`.
- Suite runs still use the existing test case runner callback chain.
- Workflow replay still reuses the existing safe replay helper and only uses stored input when available.
- Prompt comparison still calls its test case runner callback from `app/main.py`.

## Validation

This pass should be verified with:

- `python -m py_compile main.py app/main.py app/test_routes.py`
- `python -m compileall app`
- Targeted TestClient smoke checks for test case list/create/edit/delete/run surfaces, suite list/membership/run surfaces, workflow replay/test-case creation route presence, normal-user denial, and adjacent prompt comparison behavior.

## Remaining Route Groups

Future route split passes can move one bounded group at a time:

- Logs, workflow trace, reports, and regression dashboard routes
- API key, settings, and local system/process routes
- Controlled AI endpoint routes
