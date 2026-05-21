# Module Extraction Pass v2E

## Purpose

This pass moves Prompt Version Manager helper logic out of `app/main.py` with zero intended behavior change.

Routes remain in `app/main.py`; route handlers now call imported helpers from `app/prompts.py`.

## Modules Extracted

### `app/prompts.py`

`app/prompts.py` now owns prompt manager helper logic:

- default prompt version seeding
- active prompt lookup
- prompt lookup by id
- endpoint/prompt row selection
- prompt template rendering
- prompt metadata construction
- standard prompt message construction
- cmms-intake multi-part prompt message construction
- active prompt info serialization
- prompt version listing
- prompt version create/patch/archive helpers
- prompt activation helper using the existing promotion gate
- prompt test helper

### `app/config.py`

`app/config.py` now also provides prompt-related shared constants:

- `MODEL_NAME`
- `SUPPORTED_PROMPT_ENDPOINTS`
- `DEFAULT_PROMPT_VERSIONS`

## Callback Injection Strategy

The prompt test helper still needs to execute the currently configured model call and optionally load environment code lists.

To avoid importing `app.main`:

- `app/prompts.py` accepts `call_ollama` as an explicit callback for prompt tests.
- `app/prompts.py` accepts `get_environment_values` as an explicit callback for prompt tests.
- `app/main.py` supplies these callbacks from the existing AI orchestration layer.

## Circular Import Strategy

`app/prompts.py` does not import `app.main`.

- It imports shared constants from `app.config`.
- It imports DB helpers from `app.db`.
- It imports promotion gate/audit helpers from `app.prompt_promotions`.
- `app/main.py` imports prompt helpers and keeps routes plus AI endpoint orchestration.

## Preserved Behavior

This pass intentionally does not change:

- API routes or HTTP methods
- API response shapes
- database schema
- prompt text
- prompt activation gate behavior
- prompt archive guard behavior
- prompt test behavior
- cmms-intake prompt selection
- prompt version recorded in workflow traces
- test case, suite, comparison, promotion, and regression dashboard behavior
- admin/user authorization behavior

## Validation

Completed after this pass:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app/main.py app/prompts.py app/config.py
.\.venv\Scripts\python.exe -m compileall app
```

Both commands passed.

Smoke checks completed with deterministic fake Ollama responses and FastAPI `TestClient`:

- `/ui` loads
- admin login works
- active prompt info works
- prompt version list works
- prompt create/patch/test/archive works
- archived prompt edit guard still returns error
- cmms-intake still works
- saved test case run works
- test suite run works
- prompt comparison works
- promotion gate works
- regression dashboard works
- normal user still receives `403` for prompt admin endpoints
- no `/chat`, LLM judge, multi-agent, backend audio/upload/speech, CMMS write-back, or email route was added

## Remaining Monolith Areas

Large areas still live in `app/main.py`:

- auth and sessions
- API key management
- environment and code list management
- AI endpoint orchestration
- UI HTML and JavaScript

## Safety Notes

No multi-agent logic, LLM judge, router agent, reviewer agent, code normalization agent, CMMS write-back, or email sending was added in this pass.
