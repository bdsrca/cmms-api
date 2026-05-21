# Route Split v3B

## Purpose

Move authentication and portal user-administration routes out of `app/main.py` into an `APIRouter` module with zero intended behavior change.

## Routes Moved

Moved from `app/main.py` to `app/auth_routes.py`:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PATCH /api/admin/users/{user_id}`

## Models Moved

- `LoginRequest`
- `UserCreateRequest`
- `UserPatchRequest`

## Modules Added

- `app/auth_routes.py`
  - Defines an `APIRouter`
  - Owns auth and portal user admin route registration
  - Delegates password/session behavior to `app.security`
  - Uses `current_admin` for user-management authorization

## Main Wiring

`app/main.py` now imports and registers:

```python
from .auth_routes import router as auth_router

app.include_router(auth_router)
```

## Behavior Preserved

- Login and logout paths are unchanged.
- Session cookie behavior remains owned by `app.security.login_user` and `app.security.logout_user`.
- Login rate limiting remains unchanged.
- Password hashing and password verification remain unchanged.
- Admin-only user management remains guarded server-side by `current_admin`.
- User list, create, and patch response shapes are unchanged.

## Why This Route Group

Auth and user routes are more sensitive than the v3A core routes, but their domain logic was already centralized in `app.security`. Moving route registration now reduces `app/main.py` size while keeping security behavior in the same helper layer.

## Validation Results

- `python -m py_compile main.py app/main.py app/auth_routes.py app/security.py`
- `python -m compileall app`
- Targeted smoke test passed for:
  - `/ui` load
  - failed login returns `401`
  - successful admin login sets session cookie
  - admin user list
  - admin user create
  - admin user patch
  - logout clears session
  - logged-out `/api/me` returns `401`
  - normal user denied `GET /api/admin/users`
  - normal user denied `POST /api/admin/users`
  - auth/user routes are registered with expected methods
  - no `/chat`, LLM judge, backend audio upload/speech, CMMS write-back, or email route added

## Remaining Route Groups

Future route split passes can move:

- Environment/code-list routes
- Validation and output contract routes
- Prompt/test-case/test-suite/regression routes
- AI endpoint routes
- System/process routes

Those should move one group at a time with targeted smoke tests.
