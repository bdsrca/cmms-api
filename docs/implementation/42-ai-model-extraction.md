# AI Model Extraction

## Purpose

Move the controlled AI request and response Pydantic models out of the FastAPI
assembly module after the route split closeout.

## Change

`app/models.py` now owns the shared models used by AI route wiring:

- text, extraction, and email intake request payloads
- summarize, assistant, extraction, and intake response payloads
- nested intake fields, validation, and draft response models

`app/main.py` imports those models and continues to inject them into
`app/ai_routes.py`, so route paths, auth requirements, and response shapes stay
unchanged.

## Compatibility

The email intake source guard now checks `app/models.py` for
`EmailIntakeRequest`. That keeps the guard focused on the model owner after the
extraction instead of tying it to the FastAPI assembly module.

Root `main.py` remains the `uvicorn main:app` compatibility wrapper.

## Validation

Verify this pass with:

- `python -m py_compile main.py app/main.py app/models.py`
- `python -m compileall app`
- `python -m unittest tests.test_email_intake_api`
- targeted AI route smoke checks for email intake and CMMS intake
