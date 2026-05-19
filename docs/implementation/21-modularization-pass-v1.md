# Modularization Pass v1

## Purpose

The portal had grown into a very large root `main.py` containing routing, database setup, auth, AI endpoint orchestration, validation, regression tooling, and UI HTML.

Modularization Pass v1 creates a Python package structure and preserves the existing root import/launch behavior with zero intended runtime behavior change.

## Before

```text
main.py
```

Root `main.py` contained the complete application.

## After

```text
main.py                  # compatibility wrapper
app/
  __init__.py
  main.py                # current implementation and FastAPI app
  config.py
  db.py
  security.py
  models.py
  api_keys.py
  workflow_trace.py
  environments.py
  validation_rules.py
  output_contracts.py
  prompts.py
  test_cases.py
  test_suites.py
  prompt_comparisons.py
  prompt_promotions.py
  regression_dashboard.py
  ai_endpoints.py
  ui.py
```

The root wrapper imports `app.main` and aliases `sys.modules["main"]` to the implementation module. This preserves:

- `uvicorn main:app`
- `import main`
- existing smoke tests that monkeypatch functions on `main`

## Modules Created

The new module files are compatibility facades in v1. They define stable import boundaries for the next extraction pass while re-exporting the current implementation from `app.main`.

This avoids changing route behavior, auth behavior, schema behavior, prompt behavior, or validation behavior during the first package split.

## Preserved Behavior

No intended behavior changed:

- existing paths and methods are unchanged
- root `main.py` still works
- database path remains project-root `data/portal.db`
- log path remains project-root `logs/cmms-llm-api.log`
- active prompt is not changed
- validation rules and output contracts are not changed
- no new AI workflow, LLM judge, CMMS write-back, or email behavior was added

## Validation Results

Run in this pass:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py
.\.venv\Scripts\python.exe -m py_compile app\main.py
.\.venv\Scripts\python.exe -m compileall app
```

Additional smoke checks verify `/ui`, login, `cmms-intake`, workflow trace, output contract validation, environment validation, prompt comparison, promotion gate, test suites, regression dashboard, and forbidden routes.

## Known Remaining Technical Debt

- Most implementation code still lives in `app/main.py`.
- The new modules are stable facades, not fully extracted service modules yet.
- The portal HTML/JavaScript is still embedded in Python.

## Future Pass

- move implementation bodies from `app/main.py` into the facade modules
- split the UI into static assets
- add service-layer tests
- add route-level tests
- add import-cycle checks
