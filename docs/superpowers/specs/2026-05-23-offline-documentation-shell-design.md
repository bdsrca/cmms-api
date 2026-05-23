# Offline Documentation Shell Design

## Goal

Provide a useful documentation-only experience when the local FastAPI service is unavailable, without implying that the operator console, authentication, AI endpoints, system controls, or CMMS connector are usable offline.

The primary user story is: an operator or evaluator has opened the portal before, the local service later stops, and they can still read product documentation, security boundaries, API usage notes, and troubleshooting steps from the browser. A secondary launcher-oriented path can open a static offline page when health checks fail.

## Non-Goals

- Do not support offline login.
- Do not expose Dashboard, API Keys, Users, Logs, Environments, Prompts, System, AI Test Console, or CMMS connector controls while offline.
- Do not queue AI calls, CMMS pushes, admin actions, email sends, or local process controls for later replay.
- Do not cache secrets, generated API keys, authenticated API responses, logs, user records, environment records, prompts, contracts, or CMMS connector configuration.
- Do not introduce a frontend build system.

## Recommended Approach

Use a hybrid offline model:

1. Add a static offline documentation page served by the app while online.
2. Register a small service worker from `/ui` that caches only safe public assets.
3. Let the service worker return the offline documentation shell when navigation to `/ui` fails because the local service is down.
4. Keep all authenticated and operational APIs network-only.

This gives the best user experience after a first successful load, while preserving a simple static fallback that a launcher can open directly if the service never starts.

## Architecture

### Public Documentation Source

The curated public documentation data should remain server-owned and explicitly safe for unauthenticated users. The existing `/api/public/documentation` endpoint is the source of truth for online rendering.

For offline mode, duplicate only this safe documentation payload into the static offline shell or a small public JavaScript payload. The offline shell must not read from arbitrary files or authenticated endpoints.

### Offline Page

Add a route such as `/offline` that returns a self-contained static HTML page. It should use the same visual tone as the current guest documentation page:

- Clear `Service offline` status.
- Documentation cards.
- Troubleshooting steps for starting the local API, Ollama, and launcher.
- A retry button that attempts to navigate back to `/ui`.
- Disabled sign-in/operator actions with copy that explains the local API must be running.

The offline page should work as a standalone document, so it can also be saved or opened by a launcher in the future.

### Service Worker

Add a minimal service worker, for example `/offline-sw.js`, registered from `/ui` after the page loads.

Cache allowlist:

- `/offline`
- `/api/public/documentation` if using runtime docs caching
- `/ui` shell, only if the current response is a normal successful document response
- optional favicon response

Network-only denylist:

- `/auth/*`
- `/api/me`
- `/api/default-api-key`
- `/api/admin/*`
- `/api/ai/*`
- `/api/environments*`
- `/api/kb/status`
- `/api/system/*`
- any route not explicitly allowlisted

For navigation requests, the service worker should try the network first. If the request fails and a cached offline page exists, return `/offline`. For API requests, it should not synthesize success responses for protected or operational routes.

## UI Behavior

### Online Unauthenticated

Behavior remains as recently added:

- Show login card.
- Show `Browse documentation`.
- Fetch `/api/public/documentation`.
- Do not show authenticated navigation or controls.

### Online Authenticated

Behavior remains unchanged:

- Show normal app shell.
- Health text can continue to report local API state.
- Background service worker registration is silent unless it fails.

### Offline After Prior Visit

The browser shows the offline shell:

- Header/status: `Service offline`.
- Documentation is visible.
- Troubleshooting and retry controls are visible.
- Sign-in and operator controls are hidden or disabled.
- Copy clearly states that no portal session, API access, AI processing, or CMMS action is available while offline.

### First Visit While Service Is Down

The browser cannot load `http://127.0.0.1:<port>/ui` because no server exists to return HTML. This limitation should be documented in the offline page and launcher docs.

If a launcher is available, it can open the static offline page directly after a failed health check. That launcher enhancement is optional and out of scope for the first implementation.

## Security Boundaries

- Offline mode is documentation-only.
- Offline mode must not create or fake an authenticated session.
- Offline mode must not store or display API keys, cookies, secrets, logs, generated payloads, CMMS connector settings, or user data.
- Protected routes must remain protected when the service is online.
- Service worker fallback must not convert failed protected API calls into successful placeholder responses.
- The offline shell should use only hardcoded safe documentation or the curated public documentation endpoint.

## Data Flow

Online first load:

1. Browser requests `/ui`.
2. UI registers `/offline-sw.js`.
3. Service worker caches `/offline` and optionally public docs.
4. User can browse public docs or sign in normally.

Offline later:

1. Browser requests `/ui`.
2. Network request fails because the local service is unavailable.
3. Service worker returns cached `/offline`.
4. User can read offline documentation and retry the local service.

## Testing

Automated tests:

- `/offline` returns HTML without authentication.
- `/offline-sw.js` returns JavaScript with the expected allowlist/denylist markers.
- `/ui` includes service worker registration.
- Public docs remain unauthenticated.
- `/api/me`, `/api/kb/status`, `/api/admin/*`, and `/api/ai/*` remain protected or unavailable without credentials.

Browser smoke checks:

- Online `/ui` still loads.
- Unauthenticated `Browse documentation` still works.
- `/offline` renders without login.
- Simulated offline navigation falls back to the offline shell after service worker registration.
- Offline shell has no authenticated navigation or operational controls.

## Rollout

Implement in a narrow first pass:

1. Static offline documentation route.
2. Minimal service worker.
3. UI registration.
4. Tests and browser smoke verification.

Launcher integration can be a follow-up once the offline shell is stable.
