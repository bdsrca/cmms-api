# Route Split v3H: Management And System Routes

## Purpose

Move API key management, portal settings, and local system/process control routes out of `app/main.py` without changing their security boundaries or process behavior.

## Route Module

`app/management_routes.py` now owns:

- API key list, create, and patch routes
- Admin settings read and patch routes
- Local system status and system log routes
- Local Ollama start and stop routes
- Local FastAPI shutdown route
- Route-local request/response models for API keys, settings, and system status

`app/main.py` still owns the concrete process-control helpers and injects them through `build_management_router(...)`:

- local-client guard
- Ollama status/wait/start/stop helpers
- delayed FastAPI shutdown helper

This keeps route splitting separate from a process-control service refactor.

## Preserved Behavior

- Existing paths, HTTP methods, and response shapes are unchanged.
- API key and settings routes remain admin-only.
- System status, Ollama start/stop, and shutdown keep the admin and local-client guards.
- System log reads keep their current authenticated-user plus local-client boundary.
- API key values are still handled by the existing hashed key helpers.
- Cloudflare/remote process control policy is unchanged.

## Validation

This pass should be verified with:

- `python -m py_compile main.py app/main.py app/management_routes.py`
- `python -m compileall app`
- Targeted TestClient smoke checks for API key management, settings read/write, system status/log local guard behavior, Ollama route registration without starting or stopping a real process, shutdown route registration without triggering shutdown, and normal-user authorization.

## Remaining Route Group

The primary remaining route split is the controlled AI endpoint group.
