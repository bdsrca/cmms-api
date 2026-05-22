# Route Split Closeout v3J

## Purpose

Close out the route split series with a conservative cleanup pass in `app/main.py` after controlled AI routes moved to dedicated routers.

## Cleanup Applied

Removed unused helper definitions from `app/main.py` that no longer have call sites after earlier extraction work:

- Legacy inline prompt builders for summarize, assistant, extraction, classifier, field extraction, and draft generation
- Duplicate redaction / JSON / timestamp / result-value helpers already owned by extracted domain modules

The active AI pipeline remains in `app/ai_endpoints.py`, prompt version behavior remains in `app/prompts.py`, and test/comparison helpers keep their own serialization helpers.

## Preserved Main Responsibilities

`app/main.py` still intentionally owns:

- FastAPI app assembly and router inclusion
- Startup/shutdown and request logging middleware
- Shared request/response model compatibility surface for current AI routes
- Process-control callback implementations injected into management routes
- AI endpoint test runner callback glue used by saved test cases and prompt comparisons

## Validation

This cleanup should be verified with:

- `python -m py_compile main.py app/main.py`
- `python -m compileall app`
- Targeted AI route smoke through the router callback path
- Existing email intake source-level unit test

## Follow-Up

A future bounded pass may move the AI request/response Pydantic models from `app/main.py` into `app/models.py` once the remaining source-level compatibility checks are updated together.
