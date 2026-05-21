# Module Extraction Pass v2J

## Purpose

Move the FastAPI-served portal UI HTML/CSS/JavaScript out of `app/main.py` into `app/ui.py` with zero intended behavior change.

## Functions Moved

- `PORTAL_HTML`
- Portal HTML/CSS/JavaScript document assembly
- `render_portal_html`

## Modules Extracted

- `app/ui.py` now owns the static portal document string.
- `app/main.py` keeps the existing `/ui` route and returns `HTMLResponse(render_portal_html())`.

## Strategy

The existing portal document was moved as one raw string block to avoid accidentally changing JavaScript IDs, functions, CSS classes, or template-string behavior.

No UI behavior was intentionally changed.

## Behavior Preserved

- `/ui` route path is unchanged.
- `/ui` response type is unchanged.
- Existing login, dashboard, environment, code list, validation rules, output contracts, prompts, test console, voice demo, logs, and regression dashboard client-side code remains unchanged.

## Validation Results

- `python -m py_compile main.py app/main.py app/ui.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/ui` response loads
  - key portal markers remain present in HTML/JS
  - admin login
  - mocked `cmms-intake` with trace
  - regression dashboard
  - normal user denied admin regression dashboard
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Monolith Areas

- FastAPI route registration still mostly lives in `app/main.py`.
- Pydantic route models still mostly live in `app/main.py`.

Future passes can split route groups with `APIRouter` once the static UI and domain helpers are stable.
