# Route Split v3D

## Purpose

Move Validation Rules and Output Contracts routes out of `app/main.py` into an `APIRouter` module with zero intended behavior change.

## Routes Moved

Moved from `app/main.py` to `app/validation_contract_routes.py`:

- `GET /api/environments/{environment_code}/validation-rules`
- `PATCH /api/admin/environments/{environment_code}/validation-rules/{rule_id}`
- `POST /api/admin/environments/{environment_code}/validation-rules/reset-defaults`
- `POST /api/environments/{environment_code}/validate-sample`
- `GET /api/output-contracts/{endpoint}`
- `GET /api/admin/output-contracts`
- `GET /api/admin/output-contracts/{endpoint}`
- `POST /api/admin/output-contracts`
- `PATCH /api/admin/output-contracts/{contract_id}`
- `POST /api/admin/output-contracts/{contract_id}/activate`
- `POST /api/admin/output-contracts/{contract_id}/validate-sample`

## Models Moved

- `ValidationRulePatchRequest`
- `ValidateSampleRequest`
- `OutputContractRequest`
- `OutputContractPatchRequest`

## Modules Added

- `app/validation_contract_routes.py`
  - Defines an `APIRouter`
  - Owns validation rules and output contract route registration
  - Delegates business behavior to `app.validation_rules` and `app.output_contracts`
  - Keeps server-side session/admin guards with `current_user` and `current_admin`

## Main Wiring

`app/main.py` now imports and registers:

```python
from .validation_contract_routes import router as validation_contract_router

app.include_router(validation_contract_router)
```

## Behavior Preserved

- Route paths are unchanged.
- HTTP methods are unchanged.
- Request model validation is unchanged.
- Validation rule view and sample validation remain available to authenticated portal users.
- Validation rule patch/reset remains admin-only.
- Output contract read remains available to authenticated portal users.
- Output contract create/patch/activate/sample validation remains admin-only.
- Validation engine and output contract engine are unchanged.

## Why This Route Group

Validation Rules and Output Contracts are closely related control-plane surfaces. Their helper logic was already extracted, so this pass moves the HTTP layer while preserving the deterministic validation gates.

## Validation Results

- `python -m py_compile main.py app/main.py app/validation_contract_routes.py app/validation_rules.py app/output_contracts.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/ui` load
  - admin login
  - validation rules list
  - validation rule patch
  - validate sample with alias normalization
  - validation rules reset defaults
  - public active output contract read
  - admin output contracts list
  - output contract create
  - output contracts by endpoint
  - output contract patch
  - output contract validate sample
  - output contract activate
  - normal user can view rules, validate sample, and read active contract
  - normal user denied admin validation rule patch
  - normal user denied admin output contract create
  - validation/contract routes registered with expected methods
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

During smoke testing, a runtime-only Pydantic annotation issue was found in metadata request models: quoted forward references were used with `| None` before the models were declared. The metadata model definitions were moved above `TextRequest`/`ExtractFieldsRequest`, and the annotations now use direct model references. No behavior change was intended.

## Remaining Route Groups

Future route split passes can move:

- Prompt/test-case/test-suite/regression routes
- AI endpoint routes
- System/process routes

Those should move one group at a time with targeted smoke tests.
