# Main Config Ownership Cleanup

## Purpose

Continue shrinking `app/main.py` as the FastAPI assembly module without
changing runtime behavior.

## Change

`app/config.py` already owns the shared model, prompt, validation, and output
contract constants used by extracted modules. `app/main.py` now imports those
constants instead of keeping duplicate prompt and contract definitions inline.

The imported names remain available from `app.main` for compatibility with
existing assembly glue and any callers that still reference the compatibility
module.

## Why This Slice

The duplicate contract copy in `app/main.py` can drift from the shared contract
owner. Keeping one owner lets the route assembly layer stay focused on:

- FastAPI app creation and router registration
- startup/shutdown hooks
- request logging middleware
- callback injection into extracted route builders

## TDD Guard

`tests/test_main_assembly.py` checks that `app.main` reuses the shared prompt
and contract objects from `app.config`.

## Validation

Verify this pass with:

- `python -m py_compile main.py app/main.py app/config.py`
- `python -m compileall app`
- `python -m unittest tests.test_main_assembly`
- focused AI route smoke for CMMS intake and email intake
