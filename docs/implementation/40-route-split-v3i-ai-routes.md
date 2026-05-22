# Route Split v3I: Controlled AI Routes

## Purpose

Move the controlled CMMS AI endpoint route layer out of `app/main.py` while preserving API key guards, response contracts, request state metadata, and the existing AI pipeline helpers.

## Route Module

`app/ai_routes.py` now owns:

- Summarize work order route
- CMMS assistant route
- Extract work order fields route
- CMMS intake route
- Email intake route

`app/main.py` still owns the existing request/response Pydantic models for this pass and injects them into `build_ai_router(...)`. That preserves the current test case runner request factory and the email-intake source compatibility surface while keeping the route module independent from `app.main`.

The router also receives the shared `route_call_ollama(...)` callback so tests can keep monkeypatching `app.main.call_ollama`.

## Preserved Behavior

- Existing route paths, HTTP methods, API key dependencies, and response models are unchanged.
- Environment code propagation on `request.state` remains unchanged.
- CMMS intake still carries API key/user metadata into the existing helper.
- Email intake still formats email text, enforces the post-format 4000 character limit, and calls CMMS intake with `source="email_api"`.
- No generic `/chat` endpoint was added.

## Validation

This pass should be verified with:

- `python -m py_compile main.py app/main.py app/ai_routes.py`
- `python -m compileall app`
- Targeted TestClient smoke checks with stubbed Ollama output for summarize, assistant, extract, CMMS intake, email intake, API key rejection, route registration, and existing email-intake source tests.

## Route Split Status

After this pass, `app/main.py` primarily retains application assembly, shared route callback wiring, startup/middleware lifecycle, AI request/response model compatibility, and the existing helper glue used by test execution.
