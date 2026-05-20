# Module Extraction Pass v2B

## Purpose

This pass moves Prompt A/B Comparison and Prompt Promotion Gate helper logic out of `app/main.py` with zero intended behavior change.

The FastAPI routes remain in `app/main.py`; the route handlers now call imported service helpers from dedicated modules.

## Modules Extracted

### `app/prompt_comparisons.py`

This module now owns Prompt A/B Comparison helper logic:

- `status_is_passing`
- `classify_prompt_comparison_result`
- `prompt_comparison_field_differences`
- `prompt_comparison_case_json`
- `prompt_comparison_summary`
- `run_prompt_comparison`
- `list_prompt_comparisons`
- `get_prompt_comparison`

`run_prompt_comparison` accepts callbacks for monolith-owned behavior that has not yet been extracted, such as `prompt_version_by_id` and `run_test_case_row`.

### `app/prompt_promotions.py`

This module now owns Prompt Promotion Gate helper logic:

- `active_prompt_for_endpoint`
- `required_suite_readiness`
- `check_prompt_promotion_gate`
- `record_prompt_promotion`
- `list_prompt_promotions`
- `get_prompt_promotion`

The existing activation route remains in `app/main.py` because it still coordinates route-level request handling and status updates.

## Circular Import Strategy

The extracted modules do not import `app.main`.

- `app/prompt_comparisons.py` imports only standard library helpers, FastAPI `HTTPException`, and `app.db`.
- `app/prompt_promotions.py` imports only standard library helpers and `app.db`.
- `app/main.py` imports the extracted helpers.
- Monolith-only functions are passed into comparison helpers as explicit callbacks.

This keeps dependency direction one-way and avoids circular imports.

## Preserved Behavior

This pass intentionally does not change:

- API routes or HTTP methods
- API response shapes
- database schema
- prompt text
- validation logic
- UI behavior
- prompt comparison classification behavior
- promotion gate rules
- override behavior
- promotion audit records
- one-active-prompt behavior
- suite readiness integration
- admin-only authorization

## Validation

Run after this pass:

```powershell
python -m py_compile main.py app/main.py app/prompt_comparisons.py app/prompt_promotions.py
python -m compileall app
```

Smoke checks should confirm:

- `/ui` loads
- admin login works
- normal users still receive `403` for admin endpoints
- prompt comparison runs and detail loads
- comparison classification remains deterministic
- promotion-check passes and blocks under the same conditions as before
- override activation still requires a reason
- promotion audit rows are recorded
- only one active prompt remains per endpoint
- existing test case, test suite, regression dashboard, and cmms-intake flows still work

## Remaining Monolith Areas

Large areas still live in `app/main.py`:

- auth and sessions
- API key management
- environment and code list management
- validation rules
- output contracts
- prompt version CRUD
- test cases and replay
- test suites
- AI endpoint orchestration
- UI HTML and JavaScript

## Safety Notes

No multi-agent logic, LLM judge, router agent, reviewer agent, code normalization agent, CMMS write-back, or email sending was added in this pass.
