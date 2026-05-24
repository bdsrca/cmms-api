# Offline Documentation Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a documentation-only offline shell that can be shown after the local portal has been visited once and the local FastAPI service later becomes unavailable.

**Architecture:** Keep the online portal in `app/ui.py`, add focused offline rendering helpers in a new `app/offline_ui.py`, and expose `/offline`, `/offline-sw.js`, and a safe `/api/public/status` availability endpoint from `app/core_routes.py`. The service worker caches only public documentation resources and falls back to `/offline` for failed document navigation; protected and operational APIs remain network-only.

**Tech Stack:** FastAPI, Pydantic models already in `app/core_routes.py`, plain HTML/CSS/JavaScript, browser Service Worker API, pytest with FastAPI `TestClient`.

---

### Task 1: Add Tests For Offline Documentation Routes

**Files:**
- Create: `tests/test_offline_documentation_shell.py`

- [ ] **Step 1: Write the failing route and UI registration tests**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_offline_page_is_public_documentation_only() -> None:
    response = TestClient(app).get("/offline")

    assert response.status_code == 200
    html = response.text
    assert "Service offline" in html
    assert "Operator Console Overview" in html
    assert "Retry local portal" in html
    assert "apiStatusLight" in html
    assert "modelStatusLight" in html
    assert "refreshOfflineStatus" in html
    assert "/api/public/status" in html
    assert "status-green" in html
    assert "status-red" in html
    assert 'id="appView"' not in html
    assert 'onclick="login()"' not in html
    assert "/api/admin/" not in html
    assert "/api/ai/" not in html


def test_public_availability_status_is_safe_without_account() -> None:
    response = TestClient(app).get("/api/public/status")

    assert response.status_code == 200
    data = response.json()
    assert data["api_available"] is True
    assert isinstance(data["model_available"], bool)
    assert data["model"]
    assert "log_file" not in data
    assert "api_key" not in data


def test_offline_service_worker_has_safe_cache_and_network_only_boundaries() -> None:
    response = TestClient(app).get("/offline-sw.js")

    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    script = response.text
    assert "/offline" in script
    assert "/api/public/documentation" in script
    assert "/auth/" in script
    assert "/api/me" in script
    assert "/api/admin/" in script
    assert "/api/ai/" in script
    assert "/api/system/" in script
    assert "/api/kb/status" in script
    assert 'event.request.mode === "navigate"' in script


def test_ui_registers_offline_service_worker() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    html = response.text
    assert "registerOfflineShell" in html
    assert 'navigator.serviceWorker.register("/offline-sw.js")' in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_offline_documentation_shell.py -q
```

Expected: failures because `/offline`, `/api/public/status`, `/offline-sw.js`, and service worker registration do not exist yet.

---

### Task 2: Add Focused Offline Rendering Helpers

**Files:**
- Create: `app/offline_ui.py`

- [ ] **Step 1: Implement static offline HTML and service worker rendering**

Create `app/offline_ui.py` with these public functions:

```python
"""Static offline documentation shell rendering."""

from html import escape
from typing import Protocol, Sequence


class PublicDocLike(Protocol):
    slug: str
    title: str
    summary: str
    sections: list[str]


def render_offline_html(docs: Sequence[PublicDocLike]) -> str:
    cards = "\n".join(_doc_card(doc) for doc in docs)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CMMS LLM Documentation Offline</title>
  <style>
    :root {{ --accent:#635bff; --text:#111827; --muted:#64748b; --line:#e5e7eb; --bg:#f7f7f8; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:"Segoe UI", Arial, sans-serif; background:var(--bg); color:var(--text); }}
    main {{ width:min(1080px, 100%); margin:0 auto; padding:34px clamp(18px, 4vw, 48px); display:grid; gap:18px; }}
    .top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:18px; padding-bottom:8px; }}
    h1 {{ margin:0 0 8px; font-size:30px; letter-spacing:0; }}
    p {{ margin:0; line-height:1.5; }}
    .muted {{ color:var(--muted); font-size:14px; }}
    .badge {{ display:inline-flex; align-items:center; border:1px solid #fed7aa; background:#fff7ed; color:#9a3412; border-radius:999px; padding:5px 10px; font-size:12px; font-weight:700; white-space:nowrap; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px; }}
    .card {{ background:#fff; border:1px solid var(--line); border-radius:16px; box-shadow:0 1px 2px rgba(16,24,40,.05); padding:18px; }}
    .card h2 {{ margin:0 0 8px; font-size:16px; letter-spacing:0; }}
    .card ul {{ margin:14px 0 0; padding-left:18px; color:#475569; line-height:1.5; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; }}
    a.button {{ display:inline-flex; min-height:38px; align-items:center; justify-content:center; border-radius:10px; padding:8px 14px; background:linear-gradient(180deg, #6d66ff, #554cf2); color:#fff; text-decoration:none; font-weight:700; }}
    .secondary {{ background:#fff; color:#111827; border:1px solid #d8dce3; box-shadow:0 1px 2px rgba(16,24,40,.05); }}
    @media (max-width: 700px) {{ .top {{ display:grid; }} }}
  </style>
</head>
<body>
  <main>
    <section class="top">
      <div>
        <h1>Documentation</h1>
        <p class="muted">The local API is unavailable, so only cached public documentation is shown.</p>
      </div>
      <div class="status-stack" aria-label="Availability status">
        <span id="shellStatusBadge" class="badge">Service offline</span>
        <div class="status-cluster">
          <div class="status-item"><span class="status-label"><span id="apiStatusLight" class="status-light status-red"></span>Local API</span><strong id="apiStatusText">Offline</strong></div>
          <div class="status-item"><span class="status-label"><span id="modelStatusLight" class="status-light status-red"></span>Local model</span><strong id="modelStatusText">Unavailable</strong></div>
        </div>
      </div>
    </section>
    <section class="card">
      <h2>Offline boundary</h2>
      <p class="muted">No portal session, AI processing, CMMS action, email sending, system control, or authenticated API access is available while the service is offline.</p>
    </section>
    <section class="grid">{cards}</section>
    <section class="card">
      <h2>Troubleshooting</h2>
      <ul>
        <li>Start the local FastAPI service or launcher, then retry the portal.</li>
        <li>Confirm Ollama is running before using AI workflows.</li>
        <li>If this is the first visit on this browser, the server must run once before offline caching can work.</li>
      </ul>
      <div class="actions" style="margin-top:14px">
        <a class="button" href="/ui">Retry local portal</a>
        <a class="button secondary" href="/offline">Reload offline docs</a>
      </div>
    </section>
  </main>
  <script>
    function refreshOfflineStatus() {
      fetch("/api/public/status", { cache: "no-store" }).catch(() => {});
    }
    window.addEventListener("load", refreshOfflineStatus);
  </script>
</body>
</html>"""


def render_offline_service_worker() -> str:
    return r'''const CACHE_NAME = "cmms-offline-docs-v1";
const OFFLINE_URL = "/offline";
const CACHE_URLS = [OFFLINE_URL, "/api/public/documentation", "/favicon.ico"];
const NETWORK_ONLY_PREFIXES = ["/auth/", "/api/admin/", "/api/ai/", "/api/system/", "/api/environments"];
const NETWORK_ONLY_PATHS = ["/api/me", "/api/default-api-key", "/api/kb/status"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CACHE_URLS)).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)))
    )
  );
  self.clients.claim();
});

function isNetworkOnly(url) {
  return NETWORK_ONLY_PATHS.includes(url.pathname) ||
    NETWORK_ONLY_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

function cachePublicResponse(request, response) {
  if (!response || !response.ok) return response;
  const copy = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).catch(() => undefined);
  return response;
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => cachePublicResponse(event.request, response))
        .catch(() => caches.match(OFFLINE_URL).then((cached) => cached || Response.error()))
    );
    return;
  }

  if (isNetworkOnly(url)) return;

  if (CACHE_URLS.includes(url.pathname)) {
    event.respondWith(
      fetch(event.request)
        .then((response) => cachePublicResponse(event.request, response))
        .catch(() => caches.match(event.request))
    );
  }
});'''


def _doc_card(doc: PublicDocLike) -> str:
    sections = "".join(f"<li>{escape(section)}</li>" for section in doc.sections)
    return (
        '<article class="card">'
        f"<h2>{escape(doc.title)}</h2>"
        f'<p class="muted">{escape(doc.summary)}</p>'
        f"<ul>{sections}</ul>"
        "</article>"
    )
```

- [ ] **Step 2: Run py_compile for the new helper**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app\offline_ui.py
```

Expected: exit code 0.

---

### Task 3: Wire Offline Routes And Public Status Into Core Routes

**Files:**
- Modify: `app/core_routes.py`

- [ ] **Step 1: Import HTTPX and the offline render helpers**

Add these imports:

```python
import httpx

from .offline_ui import render_offline_html, render_offline_service_worker
```

- [ ] **Step 2: Add the public availability response model**

Add this model after `PublicDocumentationItem`:

```python
class PublicAvailabilityResponse(BaseModel):
    service: str
    model: str
    api_available: bool
    model_available: bool
```

- [ ] **Step 3: Add `/offline` and `/offline-sw.js` routes**

Insert after the existing `/ui` route:

```python
@router.get("/offline", response_class=HTMLResponse)
async def offline() -> HTMLResponse:
    return HTMLResponse(render_offline_html(PUBLIC_DOCUMENTATION))


@router.get("/offline-sw.js")
async def offline_service_worker() -> Response:
    return Response(
        render_offline_service_worker(),
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
```

- [ ] **Step 4: Add `/api/public/status` and the local model probe**

Insert after `public_documentation()`:

```python
@router.get("/api/public/status", response_model=PublicAvailabilityResponse)
async def public_status() -> PublicAvailabilityResponse:
    return PublicAvailabilityResponse(
        service=SERVICE_NAME,
        model=MODEL_NAME,
        api_available=True,
        model_available=await local_model_available(),
    )


async def local_model_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True
```

- [ ] **Step 5: Run the offline route tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_offline_documentation_shell.py -q
```

Expected: only the `/ui` service worker registration assertion still fails.

---

### Task 4: Register The Service Worker From `/ui`

**Files:**
- Modify: `app/ui.py`

- [ ] **Step 1: Add a registration helper in the portal script**

Add this function near `renderPublicDoc`:

```javascript
    function registerOfflineShell() {
      if (!("serviceWorker" in navigator)) return;
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/offline-sw.js").catch(() => {});
      });
    }
```

- [ ] **Step 2: Call the helper before `boot()`**

Replace the final script call:

```javascript
    boot();
```

with:

```javascript
    registerOfflineShell();
    boot();
```

- [ ] **Step 3: Run the offline route and UI tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_offline_documentation_shell.py tests\test_public_documentation_access.py tests\test_progressive_console_ui.py -q
```

Expected: all selected tests pass.

---

### Task 5: Verification And Browser Smoke

**Files:**
- Verify: `app/core_routes.py`
- Verify: `app/offline_ui.py`
- Verify: `app/ui.py`
- Verify: `tests/test_offline_documentation_shell.py`

- [ ] **Step 1: Compile touched Python files**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app\core_routes.py app\offline_ui.py app\ui.py
```

Expected: exit code 0.

- [ ] **Step 2: Run security-adjacent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_offline_documentation_shell.py tests\test_public_documentation_access.py tests\test_security_review_fixes.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Browser smoke online and offline pages**

Start the local app on a free port, then use Playwright:

1. Navigate to `/ui`.
2. Confirm the login view still appears.
3. Click `Browse documentation`.
4. Confirm documentation cards appear and `appView` is hidden.
5. Navigate to `/offline`.
6. Confirm `Service offline`, `Retry local portal`, and documentation cards appear.
7. Confirm no authenticated nav or login form is visible on `/offline`.

- [ ] **Step 4: Clean generated browser artifacts**

Remove only Playwright snapshot files generated during this verification:

```powershell
Remove-Item -LiteralPath .playwright-mcp\<generated-file>.yml -ErrorAction SilentlyContinue
```

- [ ] **Step 5: Commit the implementation**

Stage only files from this implementation:

```powershell
git add -- app/core_routes.py app/offline_ui.py app/ui.py tests/test_offline_documentation_shell.py docs/superpowers/plans/2026-05-23-offline-documentation-shell.md
git commit -m "feat: add offline documentation shell"
```
