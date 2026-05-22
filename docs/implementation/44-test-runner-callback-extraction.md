# Test Runner Callback Extraction

## Purpose

Continue reducing `app/main.py` assembly glue after the route split work.

## Change

`app/test_runner_callbacks.py` now owns the callback closures used by:

- saved test case runners
- saved test suite runners
- prompt comparison test case execution

`app/main.py` still owns the AI endpoint test runner that preserves the local
`call_ollama` monkeypatch seam. It now passes that endpoint runner into
`build_test_runner_callbacks(...)` and injects the returned callbacks into the
existing route builders.

## Boundaries

This pass does not change:

- test case, suite, comparison, or workflow trace behavior
- prompt behavior
- route paths or auth requirements
- database schema

## TDD Guard

`tests/test_test_runner_callbacks.py` verifies the extracted callbacks keep the
endpoint runner, prompt lookup, supported endpoint list, and prompt comparison
runner wiring intact.

## Validation

Verify this pass with:

- `python -m py_compile main.py app/main.py app/test_runner_callbacks.py`
- `python -m compileall app`
- `python -m unittest tests.test_test_runner_callbacks`
- focused saved-test and AI route smoke checks
