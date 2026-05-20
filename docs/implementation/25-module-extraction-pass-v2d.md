# Module Extraction Pass v2D

## Purpose

This pass moves Environment Validation Rules and AI Output Contract helper logic out of `app/main.py` with zero intended behavior change.

Routes remain in `app/main.py`; route handlers now call imported helpers from dedicated modules.

## Modules Extracted

### `app/validation_rules.py`

`app/validation_rules.py` now owns environment validation helper logic:

- default validation rule seeding
- validation rule listing
- validation rule patching
- reset-defaults behavior
- validate-sample behavior
- `validate_ai_output`
- code, label, description, and alias matching
- normalized value construction
- validation error and warning construction

### `app/output_contracts.py`

`app/output_contracts.py` now owns output contract helper logic:

- default output contract seeding
- active contract lookup
- output contract listing and reading
- output contract create, patch, and activate helpers
- `validate_output_contract`
- contract sample validation
- strict mode handling
- additional property handling
- contract validation error construction
- skipped environment validation response construction

### `app/config.py`

`app/config.py` now provides shared extracted-module constants:

- `CODE_CATEGORIES`
- `DEFAULT_VALIDATION_RULES`
- `DEFAULT_CMMS_INTAKE_CONTRACT`

## Circular Import Strategy

The extracted modules do not import `app.main`.

- `app/validation_rules.py` imports only standard library helpers, FastAPI `HTTPException`, `app.config`, and `app.db`.
- `app/output_contracts.py` imports only standard library helpers, FastAPI `HTTPException`, `app.config`, and `app.db`.
- `app/main.py` imports helper functions from both modules and keeps routes plus AI endpoint orchestration.

## Preserved Behavior

This pass intentionally does not change:

- API routes or HTTP methods
- API response shapes
- database schema
- prompt text
- UI behavior
- validation rule behavior
- alias/code matching behavior
- output contract strict-mode behavior
- one-active-contract-per-endpoint behavior
- cmms-intake contract validation ordering
- environment validation skip behavior after contract failure
- admin/user authorization behavior

## Validation

Completed after this pass:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app/main.py app/validation_rules.py app/output_contracts.py
.\.venv\Scripts\python.exe -m compileall app
```

Both commands passed.

Smoke checks completed with deterministic fake Ollama responses and FastAPI `TestClient`:

- `/ui` loads
- admin login works
- normal user permission checks still return `403`
- validation rules list works
- validation rule patch works
- validation rules reset-defaults works
- validate-sample works
- alias normalization still works
- invalid priority returns validation issue
- output contracts list works
- output contract validate-sample works
- output contract activation still enforces one active contract
- cmms-intake works
- cmms-intake includes contract validation and `ai_validation`
- contract failure skips environment validation
- workflow trace records output contract and environment validation steps
- saved test case run works
- test suite run works
- prompt comparison works
- promotion gate works
- regression dashboard works
- no `/chat`, LLM judge, multi-agent, backend audio/upload/speech, CMMS write-back, or email route was added

## Remaining Monolith Areas

Large areas still live in `app/main.py`:

- auth and sessions
- API key management
- environment and code list management
- prompt version CRUD
- AI endpoint orchestration
- UI HTML and JavaScript

## Safety Notes

No deterministic normalization improvements, multi-agent logic, LLM judge, router agent, reviewer agent, code normalization agent, CMMS write-back, or email sending was added in this pass.
