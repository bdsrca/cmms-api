# API Key Scopes v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add endpoint and environment scopes to generated API keys so external callers can be limited to specific AI endpoints and environments.

**Architecture:** Keep admin portal sessions separate from API keys. `LLM_API_KEY` remains an environment/system AI key for compatibility, while generated API keys get explicit scope metadata stored in SQLite. AI routes call one shared scope enforcement helper before running endpoint logic.

**Tech Stack:** FastAPI, SQLite via `sqlite3`, Pydantic, existing unittest suite.

---

## File Structure

- Modify `app/db.py`
  - Add migration columns to `api_keys`.
  - Keep existing table compatible with existing databases.

- Modify `app/api_keys.py`
  - Normalize and serialize endpoint/environment scopes.
  - Include scopes in list/create/patch.
  - Store scope info on `request.state` during `require_api_key`.
  - Add `enforce_api_key_scope(request, endpoint, environment_code)`.

- Modify `app/management_routes.py`
  - Add `allowed_endpoints` and `allowed_environments` to `ApiKeyCreateRequest` and `ApiKeyPatchRequest`.

- Modify `app/ai_routes.py`
  - Call scope enforcement for all controlled AI routes.

- Modify `app/ui.py`
  - Add basic fields to API key creation/edit UI.
  - Keep generated key shown once.

- Create `tests/test_api_key_scopes.py`
  - Cover create/list/patch scope behavior and route enforcement.

- Create `docs/implementation/53-api-key-scopes-v1.md`
  - Document scope behavior, compatibility, and limitations.

---

## Scope Rules

Allowed endpoint values:

```python
{
    "summarize-work-order",
    "extract-work-order-fields",
    "cmms-intake",
    "intake/email",
    "cmms-assistant",
}
```

Allowed environment behavior:

- Empty `allowed_environments` means all environments.
- Empty `allowed_endpoints` means all controlled AI endpoints.
- Environment values are stored uppercase.
- Generated keys may call only AI endpoints, never `/api/admin/*`.
- `LLM_API_KEY` remains compatible and unrestricted for AI endpoints, but still cannot access admin session routes.

---

## Task 1: Add Scope Columns

**Files:**
- Modify: `app/db.py`
- Test: `tests/test_api_key_scopes.py`

- [ ] **Step 1: Write failing migration test**

Add to `tests/test_api_key_scopes.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class ApiKeyScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_api_key_scope_columns_exist(self) -> None:
        rows = db.db_fetchall("PRAGMA table_info(api_keys)")
        columns = {row["name"] for row in rows}

        self.assertIn("allowed_endpoints_json", columns)
        self.assertIn("allowed_environments_json", columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_api_key_scope_columns_exist
```

Expected: FAIL because columns do not exist.

- [ ] **Step 3: Implement migration**

In `app/db.py`, after existing schema migrations, add:

```python
api_key_columns = {row["name"] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
api_key_migrations = {
    "allowed_endpoints_json": "ALTER TABLE api_keys ADD COLUMN allowed_endpoints_json TEXT",
    "allowed_environments_json": "ALTER TABLE api_keys ADD COLUMN allowed_environments_json TEXT",
}
for column, statement in api_key_migrations.items():
    if column not in api_key_columns:
        conn.execute(statement)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_api_key_scope_columns_exist
```

Expected: PASS.

---

## Task 2: Normalize and Store Scopes

**Files:**
- Modify: `app/api_keys.py`
- Modify: `app/management_routes.py`
- Test: `tests/test_api_key_scopes.py`

- [ ] **Step 1: Write failing create/list test**

Append to `tests/test_api_key_scopes.py`:

```python
    def test_create_and_list_api_key_includes_scopes(self) -> None:
        from types import SimpleNamespace

        from app.api_keys import create_api_key, list_api_keys

        payload = SimpleNamespace(
            name="arc-intake",
            owner="vendor-a",
            allowed_endpoints=["cmms-intake", "intake/email"],
            allowed_environments=["default", "test"],
        )
        user = SimpleNamespace(username="admin")

        created = create_api_key(payload, user)
        rows = list_api_keys()
        row = next(item for item in rows if item["key_id"] == created["key_id"])

        self.assertEqual(row["allowed_endpoints"], ["cmms-intake", "intake/email"])
        self.assertEqual(row["allowed_environments"], ["DEFAULT", "TEST"])
        self.assertNotIn("allowed_endpoints_json", row)
        self.assertNotIn("allowed_environments_json", row)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_create_and_list_api_key_includes_scopes
```

Expected: FAIL because scopes are not persisted or serialized.

- [ ] **Step 3: Add request fields**

In `app/management_routes.py`:

```python
class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    owner: str | None = None
    allowed_endpoints: list[str] | None = None
    allowed_environments: list[str] | None = None


class ApiKeyPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    allowed_endpoints: list[str] | None = None
    allowed_environments: list[str] | None = None
```

- [ ] **Step 4: Add scope helpers and persistence**

In `app/api_keys.py`, add:

```python
ALLOWED_AI_ENDPOINTS = {
    "summarize-work-order",
    "extract-work-order-fields",
    "cmms-intake",
    "intake/email",
    "cmms-assistant",
}


def normalize_allowed_endpoints(values: Any) -> list[str]:
    if not values:
        return []
    result = []
    seen = set()
    for raw in values:
        endpoint = str(raw or "").strip()
        if not endpoint:
            continue
        if endpoint not in ALLOWED_AI_ENDPOINTS:
            raise HTTPException(status_code=422, detail=f"Unsupported API key endpoint scope: {endpoint}")
        if endpoint not in seen:
            result.append(endpoint)
            seen.add(endpoint)
    return result


def normalize_allowed_environments(values: Any) -> list[str]:
    if not values:
        return []
    result = []
    seen = set()
    for raw in values:
        env = str(raw or "").strip().upper()
        if not env:
            continue
        if env not in seen:
            result.append(env)
            seen.add(env)
    return result


def scope_json(values: list[str]) -> str | None:
    return json.dumps(values) if values else None


def scope_list(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def public_api_key_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    endpoints = scope_list(data.pop("allowed_endpoints_json", None))
    environments = scope_list(data.pop("allowed_environments_json", None))
    data["allowed_endpoints"] = endpoints
    data["allowed_environments"] = environments
    return data
```

Update `list_api_keys()` query to select the two new columns and return `public_api_key_row(row)`.

Update `create_api_key()` insert to include:

```python
allowed_endpoints = normalize_allowed_endpoints(getattr(payload, "allowed_endpoints", None))
allowed_environments = normalize_allowed_environments(getattr(payload, "allowed_environments", None))
```

and insert `scope_json(allowed_endpoints)` / `scope_json(allowed_environments)`.

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_create_and_list_api_key_includes_scopes
```

Expected: PASS.

---

## Task 3: Enforce Endpoint and Environment Scopes

**Files:**
- Modify: `app/api_keys.py`
- Modify: `app/ai_routes.py`
- Test: `tests/test_api_key_scopes.py`

- [ ] **Step 1: Write failing enforcement test**

Append to `tests/test_api_key_scopes.py`:

```python
    def test_scope_enforcement_blocks_wrong_endpoint_and_environment(self) -> None:
        from types import SimpleNamespace

        from fastapi import Request
        from starlette.datastructures import Headers

        from app.api_keys import create_api_key, enforce_api_key_scope, require_api_key

        payload = SimpleNamespace(
            name="arc-intake",
            owner=None,
            allowed_endpoints=["cmms-intake"],
            allowed_environments=["ARC"],
        )
        created = create_api_key(payload, SimpleNamespace(username="admin"))

        scope = {"type": "http", "headers": [(b"x-api-key", created["api_key"].encode("utf-8"))]}
        request = Request(scope)
        require_api_key(request, created["api_key"])

        enforce_api_key_scope(request, "cmms-intake", "ARC")

        with self.assertRaises(Exception) as endpoint_error:
            enforce_api_key_scope(request, "summarize-work-order", "ARC")
        self.assertEqual(getattr(endpoint_error.exception, "status_code", None), 403)

        with self.assertRaises(Exception) as env_error:
            enforce_api_key_scope(request, "cmms-intake", "DEFAULT")
        self.assertEqual(getattr(env_error.exception, "status_code", None), 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_scope_enforcement_blocks_wrong_endpoint_and_environment
```

Expected: FAIL because `enforce_api_key_scope` does not exist.

- [ ] **Step 3: Store scope on request state**

In `require_api_key()`, for `LLM_API_KEY`:

```python
request.state.allowed_endpoints = []
request.state.allowed_environments = []
```

For generated key rows, select scope columns and set:

```python
request.state.allowed_endpoints = scope_list(row["allowed_endpoints_json"])
request.state.allowed_environments = scope_list(row["allowed_environments_json"])
```

- [ ] **Step 4: Add enforcement helper**

In `app/api_keys.py`:

```python
def enforce_api_key_scope(request: Request, endpoint: str, environment_code: str | None = None) -> None:
    allowed_endpoints = getattr(request.state, "allowed_endpoints", [])
    allowed_environments = getattr(request.state, "allowed_environments", [])
    if allowed_endpoints and endpoint not in allowed_endpoints:
        raise HTTPException(status_code=403, detail="API key is not allowed to call this endpoint")
    env = str(environment_code or "").strip().upper()
    if allowed_environments and env and env not in allowed_environments:
        raise HTTPException(status_code=403, detail="API key is not allowed to use this environment")
```

- [ ] **Step 5: Call enforcement in AI routes**

In `app/ai_routes.py`, import `enforce_api_key_scope`.

Add before each helper call:

```python
enforce_api_key_scope(request, "summarize-work-order", payload.environment_code)
enforce_api_key_scope(request, "cmms-assistant", payload.environment_code)
enforce_api_key_scope(request, "extract-work-order-fields", payload.environment_code)
enforce_api_key_scope(request, "cmms-intake", payload.environment_code)
enforce_api_key_scope(request, "intake/email", payload.environment_code)
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_scope_enforcement_blocks_wrong_endpoint_and_environment
```

Expected: PASS.

---

## Task 4: Patch Scopes

**Files:**
- Modify: `app/api_keys.py`
- Test: `tests/test_api_key_scopes.py`

- [ ] **Step 1: Write failing patch test**

Append to `tests/test_api_key_scopes.py`:

```python
    def test_patch_api_key_updates_scopes(self) -> None:
        from types import SimpleNamespace

        from app.api_keys import create_api_key, list_api_keys, patch_api_key

        created = create_api_key(
            SimpleNamespace(name="limited", owner=None, allowed_endpoints=["cmms-intake"], allowed_environments=["DEFAULT"]),
            SimpleNamespace(username="admin"),
        )

        patch_api_key(
            created["key_id"],
            SimpleNamespace(name=None, enabled=None, allowed_endpoints=["summarize-work-order"], allowed_environments=["TEST"]),
        )
        row = next(item for item in list_api_keys() if item["key_id"] == created["key_id"])

        self.assertEqual(row["allowed_endpoints"], ["summarize-work-order"])
        self.assertEqual(row["allowed_environments"], ["TEST"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_patch_api_key_updates_scopes
```

Expected: FAIL because patch ignores scopes.

- [ ] **Step 3: Implement patch support**

In `patch_api_key()`, compute:

```python
existing_endpoints = scope_list(row["allowed_endpoints_json"])
existing_environments = scope_list(row["allowed_environments_json"])
allowed_endpoints = (
    normalize_allowed_endpoints(payload.allowed_endpoints)
    if getattr(payload, "allowed_endpoints", None) is not None
    else existing_endpoints
)
allowed_environments = (
    normalize_allowed_environments(payload.allowed_environments)
    if getattr(payload, "allowed_environments", None) is not None
    else existing_environments
)
```

Update SQL to set both scope columns.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_patch_api_key_updates_scopes
```

Expected: PASS.

---

## Task 5: UI and Documentation

**Files:**
- Modify: `app/ui.py`
- Create: `docs/implementation/53-api-key-scopes-v1.md`
- Test: `tests/test_api_key_scopes.py`

- [ ] **Step 1: Write UI source test**

Append to `tests/test_api_key_scopes.py`:

```python
    def test_api_key_ui_exposes_scope_fields(self) -> None:
        html = Path("app/ui.py").read_text(encoding="utf-8")

        self.assertIn("kAllowedEndpoints", html)
        self.assertIn("kAllowedEnvironments", html)
        self.assertIn("allowed_endpoints", html)
        self.assertIn("allowed_environments", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_api_key_ui_exposes_scope_fields
```

Expected: FAIL because UI fields do not exist.

- [ ] **Step 3: Add UI fields**

In `keys()` in `app/ui.py`, update Generate key card:

```html
<label>Allowed endpoints</label>
<input id="kAllowedEndpoints" placeholder="cmms-intake, intake/email">
<label>Allowed environments</label>
<input id="kAllowedEnvironments" placeholder="DEFAULT, TEST">
```

Update `createKey()`:

```javascript
function csvList(value) {
  return String(value || "").split(",").map(v => v.trim()).filter(Boolean);
}

async function createKey() {
  const data = await api("/api/admin/api-keys", {
    method: "POST",
    body: JSON.stringify({
      name: $("kName").value,
      allowed_endpoints: csvList($("kAllowedEndpoints").value),
      allowed_environments: csvList($("kAllowedEnvironments").value)
    })
  });
  $("kOut").textContent = JSON.stringify(data, null, 2);
}
```

- [ ] **Step 4: Create docs**

Create `docs/implementation/53-api-key-scopes-v1.md`:

```markdown
# API Key Scopes v1

## Purpose

Generated API keys can now be limited by AI endpoint and environment code.

## Behavior

- Empty endpoint scope means all controlled AI endpoints.
- Empty environment scope means all environments.
- Generated keys cannot access admin routes.
- `LLM_API_KEY` remains compatible for AI endpoints but is not exposed through the portal UI.

## Supported Endpoints

- summarize-work-order
- extract-work-order-fields
- cmms-intake
- intake/email
- cmms-assistant

## Security Notes

Scopes are enforced server-side in AI routes. UI controls are only convenience.
```

- [ ] **Step 5: Run UI test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes.ApiKeyScopeTests.test_api_key_ui_exposes_scope_fields
```

Expected: PASS.

---

## Task 6: Final Verification

**Files:**
- No new code beyond previous tasks.

- [ ] **Step 1: Compile touched modules**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\main.py app\db.py app\api_keys.py app\management_routes.py app\ai_routes.py app\ui.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run API key scope tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_key_scopes
```

Expected: all tests pass.

- [ ] **Step 3: Run full suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 4: Safety grep**

Run:

```powershell
rg "/api/admin/reviewer-prompt|/chat|LLM judge|send_email|work_order_created.*true" app tests docs
```

Expected: no new prohibited routes or behavior.

---

## Self-Review

Spec coverage:

- Endpoint scopes: Task 2, Task 3.
- Environment scopes: Task 2, Task 3.
- Admin CRUD visibility: Task 2, Task 4, Task 5.
- Backward compatibility: Scope empty means unrestricted; `LLM_API_KEY` remains accepted for AI endpoints.
- Server-side enforcement: Task 3.
- Tests and docs: Task 1 through Task 6.

Known limitation:

- v1 scopes are simple allow-lists. They do not yet enforce per-key quotas, rate limits, time windows, or per-action scopes such as `ai:cmms-intake`.
