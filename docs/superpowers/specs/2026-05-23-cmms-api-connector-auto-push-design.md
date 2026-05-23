# CMMS API Connector Auto-Push Design

## Goal

Add the smallest safe framework that lets an admin configure a CMMS REST API for an
environment and lets the backend auto-push a validated CMMS work-order payload when
strict deterministic gates pass.

This changes the project safety policy from "no automatic CMMS write-back" to
"no LLM or agent may write to CMMS directly; the backend may auto-push only through
an admin-configured connector after deterministic validation allows it."

## Non-Goals

- No generic `/chat` endpoint.
- No generic arbitrary outbound request tool.
- No direct LLM access to CMMS credentials or endpoints.
- No OAuth, refresh tokens, vendor-specific SDKs, background queue, or retry worker in v1.
- No automatic email sending or request approval.

## Safety Policy

Auto-push is allowed only when all of these are true:

- the environment has an enabled CMMS connector;
- `auto_push_enabled` is true for that connector;
- the canonical CMMS payload preview exists;
- the environment handoff preview status is `ready`;
- deterministic contract validation is valid;
- deterministic AI output validation is valid;
- deterministic work-order validation says the request can create a work order;
- safety review does not require human review;
- the payload has the minimum required CMMS fields;
- the connector endpoint is HTTPS, except localhost addresses allowed for local tests.

If any gate fails, the push is skipped or blocked and the reason is recorded.

## Configuration Model

Store one connector per environment in SQLite.

Fields:

- `environment_code`
- `enabled`
- `auto_push_enabled`
- `endpoint_url`
- `auth_type`: `bearer` or `header`
- `auth_header_name`: used only for `header`
- `secret_value`: stored locally, never returned by API responses
- `timeout_seconds`
- `created_at`
- `updated_at`

The first implementation can store `secret_value` in the local DB because the app
already runs as a local operator console. API responses and logs must mask it. A
later hardening pass can encrypt it at rest.

## Admin API

Add minimal admin-only endpoints:

- `GET /api/admin/environments/{environment_code}/cmms-connector`
- `PUT /api/admin/environments/{environment_code}/cmms-connector`
- `POST /api/admin/environments/{environment_code}/cmms-connector/test`

The `GET` endpoint returns the connector with `secret_configured: true|false`,
never the secret.

The `PUT` endpoint accepts connector settings. If `secret_value` is omitted, keep
the existing secret. If it is provided, replace the secret.

The `test` endpoint validates the configured shape and can perform a lightweight
dry-run request only when the endpoint is localhost or a clearly configured test
URL. The first implementation may return config validation only if a real test call
would add too much risk.

## Push Execution

The first runnable version uses a small service module:

- build a push decision from the workflow result and handoff preview;
- if blocked, return a structured `cmms_push` block without network activity;
- if allowed, POST the canonical payload as JSON to the configured endpoint;
- apply either `Authorization: Bearer <secret>` or a custom header;
- use a short timeout;
- parse a JSON response when available;
- record status code, external reference/id when present, and a short error summary.

The response shape is:

```json
{
  "status": "skipped|blocked|sent|failed",
  "auto_push_enabled": true,
  "connector_enabled": true,
  "environment_code": "DEFAULT",
  "blocked_reasons": [],
  "status_code": 201,
  "external_reference": "WO-12345",
  "message": "Created"
}
```

Secrets are never included.

## Integration Point

The auto-push hook runs after the existing intake workflow has produced validation
results and a canonical CMMS payload preview. It should reuse the current handoff
candidate helpers instead of creating a second mapping path.

For v1, the hook can be attached to the controlled `cmms-intake` flow only. Existing
admin handoff candidate preview remains available and should show the latest push
status when possible.

## UI

Keep the first UI small:

- add a basic admin connector section per environment;
- fields for endpoint, auth type, header name, secret, enabled, auto-push enabled;
- show masked secret status;
- show latest push status in the existing candidate/trace view if available.

No advanced mapping UI in v1. The system sends the existing canonical payload.

## Logging and Trace

Workflow trace records:

- decision status;
- blocked reasons;
- connector/environment identifiers;
- HTTP status code;
- external reference/id;
- short sanitized error message.

Logs must not include API secrets, full authorization headers, or plaintext request
credentials.

## Tests

Add focused tests before implementation:

- connector config stores and returns masked secrets;
- auth headers are built correctly without exposing secrets in returned data;
- auto-push gate blocks when disabled, missing config, invalid validation, or human
  review is required;
- auto-push gate allows only ready canonical handoff payloads;
- fake HTTP client receives one POST when all gates pass;
- fake HTTP client is not called when any gate blocks;
- failed CMMS response returns `failed` with sanitized details.

## Implementation Order

1. Add DB table and connector config helpers.
2. Add admin config API with masked secret responses.
3. Add auto-push gate and HTTP sender service with injectable HTTP client.
4. Wire the service into `cmms-intake` after validation and canonical preview.
5. Add minimal UI controls and status display.

## Open Decisions

- v1 stores connector secrets in SQLite as local app configuration. This is acceptable
  for the first runnable framework, but production hardening should add encryption
  at rest.
- v1 does not add retries. Failed pushes are visible in trace and can be retried by a
  later explicit admin action.
