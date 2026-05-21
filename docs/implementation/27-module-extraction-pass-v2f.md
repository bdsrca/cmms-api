# Module Extraction Pass v2F

## Purpose

This pass moves portal security/session helpers and API key helper logic out of `app/main.py` with zero intended behavior change.

Routes remain in `app/main.py`; route handlers now call imported helpers from `app/security.py` and `app/api_keys.py`.

## Modules Extracted

### `app/security.py`

`app/security.py` now owns portal authentication and role helper logic:

- `AuthContext`
- `PortalUser`
- password hashing and verification
- password rehash checks
- login rate limit state and helpers
- secure cookie detection
- session token lookup
- current user and admin role guards
- login helper
- logout helper
- admin bootstrap helper

### `app/api_keys.py`

`app/api_keys.py` now owns API key helper logic:

- JSON API key migration from legacy runtime state
- API key verification for `x-api-key`
- generated API key usage tracking
- API key listing
- API key creation
- API key patch/disable behavior

## Circular Import Strategy

The extracted modules do not import `app.main`.

- `app/security.py` imports only standard library helpers, FastAPI/Pydantic primitives, and `app.db`.
- `app/api_keys.py` imports only standard library helpers, FastAPI primitives, `app.db`, and `app.security` for `AuthContext` and `hash_text`.
- `app/main.py` imports the security/API key helpers and keeps routes plus orchestration.

## Preserved Behavior

This pass intentionally does not change:

- API routes or HTTP methods
- API response shapes
- database schema
- password hashing behavior
- login rate limit behavior
- session cookie behavior
- logout/session deletion behavior
- admin/user authorization behavior
- `LLM_API_KEY` compatibility for AI endpoints
- generated API key hashing, usage tracking, disable behavior, or one-time display behavior
- cmms-intake, test cases, test suites, prompt comparison, promotion gate, and regression dashboard behavior

## Validation

Completed after this pass:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app/main.py app/security.py app/api_keys.py
.\.venv\Scripts\python.exe -m compileall app
```

Both commands passed.

Smoke checks completed with deterministic fake Ollama responses and FastAPI `TestClient`:

- `/ui` loads
- admin login works
- failed login still returns `401`
- logout clears session
- normal users still receive `403` for admin endpoints
- API key list works
- API key creation returns plaintext key once
- generated API key can call `cmms-intake`
- generated API key usage count and last-used timestamp update
- disabled generated API key returns `401`
- environment `LLM_API_KEY` still works for AI endpoints
- saved test case run works
- test suite run works
- prompt comparison works
- promotion gate works
- regression dashboard works
- no `/chat`, LLM judge, multi-agent, backend audio/upload/speech, CMMS write-back, or email route was added

## Remaining Monolith Areas

Large areas still live in `app/main.py`:

- environment and code list management
- AI endpoint orchestration
- UI HTML and JavaScript
- process/system controls

## Safety Notes

No auth behavior, permission behavior, API key scope behavior, multi-agent logic, LLM judge, CMMS write-back, or email sending was added or changed in this pass.
