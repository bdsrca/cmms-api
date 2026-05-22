# Route Split v3E: Prompt Routes

## Purpose

Move Prompt Version Manager, Prompt A/B Comparison, and Prompt Promotion History routes out of `app/main.py` while preserving their API behavior and authorization boundaries.

## Route Module

`app/prompt_routes.py` now owns:

- Prompt version read, create, patch, archive, activate, test, and promotion-check routes
- Prompt comparison create, list, and detail routes
- Prompt promotion history list and detail routes
- Route-local request models for prompt version, promotion, and comparison payloads

`app/main.py` still owns the surrounding orchestration callbacks and injects them into `build_prompt_router(...)`:

- the existing `call_ollama` wrapper so prompt testing keeps the current monkeypatch seam
- `get_environment_values`
- `run_test_case_row_for_prompt_comparison`

That keeps the route module from reverse-importing `app.main`.

## Preserved Behavior

- Existing route paths and HTTP methods are unchanged.
- Active prompt info still requires an authenticated portal user.
- Prompt version writes, promotion checks, comparisons, and promotion history remain admin-only.
- Prompt test still uses the existing configured prompt helpers and Ollama callback path.
- Prompt comparisons still run through the existing saved test case callback.
- Prompt promotion gate logic remains in `app/prompt_promotions.py`.

## Validation

This pass should be verified with:

- `python -m py_compile main.py app/main.py app/prompt_routes.py`
- `python -m compileall app`
- Targeted prompt route smoke checks for login, prompt version list/detail/test, prompt comparison detail, promotion history detail, admin authorization, and adjacent Test Case / Promotion Gate behavior.

## Remaining Route Groups

Future route split passes can move one bounded group at a time:

- Test case and test suite routes
- Logs, workflow trace, reports, and regression dashboard routes
- API key, settings, and local system/process routes
- Controlled AI endpoint routes
