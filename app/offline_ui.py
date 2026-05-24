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
    .status-stack {{ display:grid; justify-items:end; gap:8px; }}
    .badge {{ display:inline-flex; align-items:center; border:1px solid #fed7aa; background:#fff7ed; color:#9a3412; border-radius:999px; padding:5px 10px; font-size:12px; font-weight:700; white-space:nowrap; }}
    .status-cluster {{ display:grid; gap:6px; min-width:190px; }}
    .status-item {{ display:flex; align-items:center; justify-content:space-between; gap:10px; border:1px solid var(--line); background:#fff; border-radius:999px; padding:6px 10px; box-shadow:0 1px 2px rgba(16,24,40,.05); font-size:12px; }}
    .status-label {{ display:flex; align-items:center; gap:7px; font-weight:700; }}
    .status-light {{ width:10px; height:10px; border-radius:999px; box-shadow:0 0 0 3px rgba(148,163,184,.12); }}
    .status-green {{ background:#16a34a; box-shadow:0 0 0 3px rgba(22,163,74,.14); }}
    .status-red {{ background:#dc2626; box-shadow:0 0 0 3px rgba(220,38,38,.14); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px; }}
    .card {{ background:#fff; border:1px solid var(--line); border-radius:16px; box-shadow:0 1px 2px rgba(16,24,40,.05); padding:18px; }}
    .card h2 {{ margin:0 0 8px; font-size:16px; letter-spacing:0; }}
    .card ul {{ margin:14px 0 0; padding-left:18px; color:#475569; line-height:1.5; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; }}
    a.button {{ display:inline-flex; min-height:38px; align-items:center; justify-content:center; border-radius:10px; padding:8px 14px; background:linear-gradient(180deg, #6d66ff, #554cf2); color:#fff; text-decoration:none; font-weight:700; }}
    a.button.secondary {{ background:#fff; color:#111827; border:1px solid #d8dce3; box-shadow:0 1px 2px rgba(16,24,40,.05); }}
    @media (max-width: 700px) {{ .top {{ display:grid; }} .status-stack {{ justify-items:start; }} }}
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
    function setAvailabilityLight(lightId, textId, available, text) {{
      const light = document.getElementById(lightId);
      const label = document.getElementById(textId);
      if (light) light.className = `status-light ${{available ? "status-green" : "status-red"}}`;
      if (label) label.textContent = text;
    }}
    async function refreshOfflineStatus() {{
      setAvailabilityLight("apiStatusLight", "apiStatusText", false, "Offline");
      setAvailabilityLight("modelStatusLight", "modelStatusText", false, "Unavailable");
      const badge = document.getElementById("shellStatusBadge");
      if (badge) badge.textContent = "Service offline";
      try {{
        const response = await fetch("/api/public/status", {{ cache: "no-store" }});
        if (!response.ok) throw new Error("status unavailable");
        const status = await response.json();
        setAvailabilityLight("apiStatusLight", "apiStatusText", true, "Online");
        setAvailabilityLight(
          "modelStatusLight",
          "modelStatusText",
          Boolean(status.model_available),
          status.model_available ? `${{status.model}} ready` : `${{status.model}} offline`
        );
        if (badge) badge.textContent = "Service online";
      }} catch {{}}
    }}
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
