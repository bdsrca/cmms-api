# API Sample Calls

Postman-style examples for the local CMMS LLM API. Use these with the local service at `http://127.0.0.1:8000`, or replace `API_BASE_URL` with your tunnel URL when an operator has started Cloudflare Tunnel manually.

The live FastAPI schema is also available at `/docs` while the service is running. This file keeps common calls copyable and public-safe.

Postman import: [`postman/local-cmms-llm-api.postman_collection.json`](postman/local-cmms-llm-api.postman_collection.json).

## Variables

```text
API_BASE_URL=http://127.0.0.1:8000
LLM_API_KEY=replace-with-a-generated-ai-key
ADMIN_COOKIE=portal_session=replace-with-admin-session-cookie
ENVIRONMENT_CODE=DEFAULT
API_SAMPLE_ENDPOINT=cmms-intake
```

## Auth Patterns

AI endpoints use an API key:

```text
x-api-key: $LLM_API_KEY
Content-Type: application/json
```

Admin and operator endpoints use the authenticated portal session cookie. They do not accept generated AI API keys as admin credentials.

```text
Cookie: $ADMIN_COOKIE
Content-Type: application/json
```

Advisory only: AI responses can produce drafts, validation results, and handoff candidates, but they do not approve requests, send email, or directly create CMMS work orders.

## Language Examples

Set the endpoint and payload once, then choose the access method you prefer.

```json
{
  "text": "The air conditioner in ARC room 205 is making loud noise.",
  "environment_code": "DEFAULT",
  "source": "text"
}
```

### curl

```bash
curl -X POST "$API_BASE_URL/api/ai/$API_SAMPLE_ENDPOINT" \
  -H "x-api-key: $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The air conditioner in ARC room 205 is making loud noise.",
    "environment_code": "DEFAULT",
    "source": "text"
  }'
```

### PowerShell

```powershell
$Headers = @{ "x-api-key" = $env:LLM_API_KEY }
$Body = @'
{
  "text": "The air conditioner in ARC room 205 is making loud noise.",
  "environment_code": "DEFAULT",
  "source": "text"
}
'@
$Response = Invoke-RestMethod `
  -Method POST `
  -Uri "$env:API_BASE_URL/api/ai/$env:API_SAMPLE_ENDPOINT" `
  -Headers $Headers `
  -ContentType "application/json" `
  -Body $Body
$Response | ConvertTo-Json -Depth 20
```

### JavaScript fetch

```javascript
const payload = {
  text: "The air conditioner in ARC room 205 is making loud noise.",
  environment_code: "DEFAULT",
  source: "text",
};

const response = await fetch(`${process.env.API_BASE_URL}/api/ai/${process.env.API_SAMPLE_ENDPOINT}`, {
  method: "POST",
  headers: {
    "x-api-key": process.env.LLM_API_KEY,
    "Content-Type": "application/json",
  },
  body: JSON.stringify(payload),
});

if (!response.ok) throw new Error(await response.text());
console.log(await response.json());
```

### Python requests

```python
import os
import requests

payload = {
    "text": "The air conditioner in ARC room 205 is making loud noise.",
    "environment_code": "DEFAULT",
    "source": "text",
}

response = requests.post(
    f"{os.environ['API_BASE_URL']}/api/ai/{os.environ['API_SAMPLE_ENDPOINT']}",
    headers={"x-api-key": os.environ["LLM_API_KEY"]},
    json=payload,
    timeout=30,
)
response.raise_for_status()
print(response.json())
```

## AI Endpoints

### POST /api/ai/cmms-intake

Purpose: run the controlled intake workflow with extraction, contract validation, environment validation, advisory drafts, safety review, and optional CMMS handoff readiness.

Auth: `x-api-key: $LLM_API_KEY`

```json
{
  "text": "The air conditioner in ARC room 205 is making loud noise.",
  "environment_code": "DEFAULT",
  "source": "text",
  "valid_buildings": ["ARC", "MAIN"],
  "valid_priorities": ["low", "normal", "urgent"]
}
```

Response shape:

```json
{
  "endpoint": "cmms-intake",
  "environment_code": "DEFAULT",
  "contract": { "valid": true },
  "result": {},
  "ai_validation": { "valid": true },
  "validation": {
    "can_create_work_order": true,
    "needs_human_review": false,
    "missing_fields": []
  },
  "drafts": {},
  "model": "qwen3:8b"
}
```

### POST /api/ai/intake/email

Purpose: turn email fields into the same controlled intake workflow, with `source` set server-side to `email_api`.

Auth: `x-api-key: $LLM_API_KEY`

```json
{
  "from_email": "tenant@example.com",
  "to_email": "maintenance@example.com",
  "subject": "Leak in ARC 205",
  "body": "There is water dripping from the ceiling near ARC room 205.",
  "environment_code": "DEFAULT"
}
```

Expected response fields match `POST /api/ai/cmms-intake`.

### POST /api/ai/cmms-assistant

Purpose: return a controlled CMMS assistant response. This is not a generic `/chat` endpoint.

Auth: `x-api-key: $LLM_API_KEY`

```json
{
  "text": "What details should I ask for before submitting this HVAC request?",
  "environment_code": "DEFAULT",
  "source": "operator_console"
}
```

Response shape:

```json
{
  "mode": "cmms-assistant",
  "response": "Ask for...",
  "model": "qwen3:8b",
  "safety": {
    "advisory_only": true,
    "work_order_created": false
  }
}
```

### POST /api/ai/extract-work-order-fields

Purpose: extract request type, location, priority, summary, missing fields, and review status.

Auth: `x-api-key: $LLM_API_KEY`

```json
{
  "text": "Please fix the broken light in MAIN lobby.",
  "environment_code": "DEFAULT",
  "source": "text"
}
```

Response shape:

```json
{
  "request_type": "maintenance",
  "building": "MAIN",
  "room": "lobby",
  "priority": "normal",
  "summary": "Broken light in MAIN lobby.",
  "missing_fields": [],
  "needs_human_review": false,
  "confidence": 0.86
}
```

### POST /api/ai/summarize-work-order

Purpose: produce a short summary string. This endpoint does not validate readiness.

Auth: `x-api-key: $LLM_API_KEY`

```json
{
  "text": "Tenant reports the sink in ARC room 205 has been leaking since this morning.",
  "environment_code": "DEFAULT",
  "source": "text"
}
```

Response shape:

```json
{
  "summary": "Sink leak reported in ARC room 205."
}
```

## Operator And Admin Endpoints

These examples require an authenticated portal session cookie.

### GET /health

```bash
curl "$API_BASE_URL/health"
```

### GET /ui

```bash
curl "$API_BASE_URL/ui"
```

### GET /favicon.ico

```bash
curl "$API_BASE_URL/favicon.ico"
```

### POST /auth/login

```bash
curl -X POST "$API_BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"replace-with-admin-password"}'
```

### POST /auth/logout

```bash
curl -X POST "$API_BASE_URL/auth/logout" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/me

```bash
curl "$API_BASE_URL/api/me" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/users

```bash
curl "$API_BASE_URL/api/admin/users" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/users

```bash
curl -X POST "$API_BASE_URL/api/admin/users" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"username":"operator","password":"replace-with-long-password","role":"user"}'
```

### PATCH /api/admin/users/{user_id}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/users/1" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"role":"user"}'
```

### GET /api/default-api-key

```bash
curl "$API_BASE_URL/api/default-api-key" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/kb/status

```bash
curl "$API_BASE_URL/api/kb/status" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/environments

```bash
curl "$API_BASE_URL/api/environments" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/environments

```bash
curl -X POST "$API_BASE_URL/api/admin/environments" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"environment_code":"DEMO","name":"Demo Environment","enabled":true}'
```

### PATCH /api/admin/environments/{environment_code}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"name":"Default Environment","enabled":true}'
```

### GET /api/admin/environments/{environment_code}/codes

```bash
curl "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/codes" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/environments/{environment_code}/codes/preview

```bash
curl -X POST "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/codes/preview" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"category":"building","values":["ARC","MAIN"],"replace":true}'
```

### POST /api/admin/environments/{environment_code}/codes/import

```bash
curl -X POST "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/codes/import" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"category":"building","values":["ARC","MAIN"],"replace":true}'
```

### PATCH /api/admin/environments/{environment_code}/codes/{code_id}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/codes/1" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"label":"Arc Building","aliases":"ARC, Arc","enabled":true}'
```

### GET /api/environments/{environment_code}/validation-rules

```bash
curl "$API_BASE_URL/api/environments/$ENVIRONMENT_CODE/validation-rules" \
  -H "Cookie: $ADMIN_COOKIE"
```

### PATCH /api/admin/environments/{environment_code}/validation-rules/{rule_id}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/validation-rules/building" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"required":true,"code_category":"building","must_match_code_list":true,"allow_unknown":false,"severity":"error"}'
```

### POST /api/admin/environments/{environment_code}/validation-rules/reset-defaults

```bash
curl -X POST "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/validation-rules/reset-defaults" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/environments/{environment_code}/validate-sample

```bash
curl -X POST "$API_BASE_URL/api/environments/$ENVIRONMENT_CODE/validate-sample" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"values":{"building":"ARC","room":"205","priority":"normal","summary":"Noisy AC unit"}}'
```

### GET /api/output-contracts/{endpoint}

```bash
curl "$API_BASE_URL/api/output-contracts/cmms-intake" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/output-contracts

```bash
curl "$API_BASE_URL/api/admin/output-contracts" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/output-contracts/{endpoint}

```bash
curl "$API_BASE_URL/api/admin/output-contracts/cmms-intake" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/output-contracts

```bash
curl -X POST "$API_BASE_URL/api/admin/output-contracts" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"endpoint":"cmms-intake","version":"v1","name":"CMMS intake contract","schema_json":{"type":"object","required":["validation","drafts"]},"strict_mode":true,"status":"draft"}'
```

### PATCH /api/admin/output-contracts/{contract_id}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/output-contracts/1" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"name":"CMMS intake contract v1","status":"draft","strict_mode":true}'
```

### POST /api/admin/output-contracts/{contract_id}/activate

```bash
curl -X POST "$API_BASE_URL/api/admin/output-contracts/1/activate" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/output-contracts/{contract_id}/validate-sample

```bash
curl -X POST "$API_BASE_URL/api/admin/output-contracts/1/validate-sample" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"values":{"validation":{"can_create_work_order":true},"drafts":{"client_reply":"Thanks, we will review this request."}}}'
```

### GET /api/admin/api-keys

```bash
curl "$API_BASE_URL/api/admin/api-keys" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/api-keys

```bash
curl -X POST "$API_BASE_URL/api/admin/api-keys" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo client","owner":"operator","allowed_endpoints":["cmms-intake","intake/email"],"allowed_environments":["DEFAULT"]}'
```

### PATCH /api/admin/api-keys/{key_id}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/api-keys/1" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"allowed_endpoints":["cmms-intake"],"allowed_environments":["DEFAULT"]}'
```

### GET /api/admin/settings/{key}

```bash
curl "$API_BASE_URL/api/admin/settings/cmms_auto_push_enabled" \
  -H "Cookie: $ADMIN_COOKIE"
```

### PATCH /api/admin/settings/{key}

```bash
curl -X PATCH "$API_BASE_URL/api/admin/settings/cmms_auto_push_enabled" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"value":"false"}'
```

### GET /api/system/status

```bash
curl "$API_BASE_URL/api/system/status" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/system/logs

```bash
curl "$API_BASE_URL/api/system/logs" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/system/ollama/start

```bash
curl -X POST "$API_BASE_URL/api/system/ollama/start" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/system/ollama/stop

```bash
curl -X POST "$API_BASE_URL/api/system/ollama/stop" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/system/shutdown

```bash
curl -X POST "$API_BASE_URL/api/system/shutdown" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/regression-dashboard

```bash
curl "$API_BASE_URL/api/admin/regression-dashboard" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/logs

```bash
curl "$API_BASE_URL/api/admin/logs" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/workflow-runs

```bash
curl "$API_BASE_URL/api/admin/workflow-runs" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/workflow-runs/{run_id}

```bash
curl "$API_BASE_URL/api/admin/workflow-runs/1" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/workflow-runs/{run_id}/metadata-review

```bash
curl "$API_BASE_URL/api/admin/workflow-runs/1/metadata-review" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/workflow-runs/{run_id}/metadata-review/apply

```bash
curl -X POST "$API_BASE_URL/api/admin/workflow-runs/1/metadata-review/apply" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"submitted_by":"Leon","submitted_email":"tenant@example.com","requested_due":"2026-05-24","building":"ARC","room":"205"}'
```

### GET /api/admin/workflow-runs/{run_id}/cmms-handoff-candidate

```bash
curl "$API_BASE_URL/api/admin/workflow-runs/1/cmms-handoff-candidate" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/reports/usage

```bash
curl "$API_BASE_URL/api/admin/reports/usage" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/environments/{environment_code}/cmms-connector

```bash
curl "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/cmms-connector" \
  -H "Cookie: $ADMIN_COOKIE"
```

### PUT /api/admin/environments/{environment_code}/cmms-connector

```bash
curl -X PUT "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/cmms-connector" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"auto_push_enabled":false,"endpoint_url":"https://cmms.example.invalid/api/work-orders","auth_type":"bearer","secret_value":"replace-with-secret","timeout_seconds":5,"http_method":"POST","success_status_codes":"200,201,202","dry_run_enabled":true,"require_metadata_review":true,"static_headers":{},"payload_root_key":null}'
```

### POST /api/admin/environments/{environment_code}/cmms-connector/test

```bash
curl -X POST "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/cmms-connector/test" \
  -H "Cookie: $ADMIN_COOKIE"
```

### POST /api/admin/environments/{environment_code}/cmms-connector/probe

```bash
curl -X POST "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/cmms-connector/probe" \
  -H "Cookie: $ADMIN_COOKIE"
```

### GET /api/admin/environments/{environment_code}/cmms-connector/push-events

```bash
curl "$API_BASE_URL/api/admin/environments/$ENVIRONMENT_CODE/cmms-connector/push-events?limit=25" \
  -H "Cookie: $ADMIN_COOKIE"
```

## Prompt And Test Management

These endpoints are admin-only. They are documented here with compact examples because request bodies are long and the live `/docs` schema is the source of truth for every optional field.

### Prompt endpoints

```text
GET  /api/prompt-versions/active/{endpoint}
GET  /api/admin/prompt-versions
GET  /api/admin/prompt-versions/{endpoint}
POST /api/admin/prompt-versions
PATCH /api/admin/prompt-versions/{prompt_id}
POST /api/admin/prompt-versions/{prompt_id}/promotion-check
POST /api/admin/prompt-versions/{prompt_id}/activate
POST /api/admin/prompt-versions/{prompt_id}/archive
POST /api/admin/prompt-versions/{prompt_id}/test
POST /api/admin/prompt-comparisons
GET  /api/admin/prompt-comparisons
GET  /api/admin/prompt-comparisons/{comparison_id}
GET  /api/admin/prompt-promotions
GET  /api/admin/prompt-promotions/{promotion_id}
```

Typical prompt test call:

```bash
curl -X POST "$API_BASE_URL/api/admin/prompt-versions/1/test" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"text":"Broken light in MAIN lobby.","environment_code":"DEFAULT"}'
```

### Test case and suite endpoints

```text
GET    /api/admin/test-cases
POST   /api/admin/test-cases
GET    /api/admin/test-cases/{test_case_id}
PATCH  /api/admin/test-cases/{test_case_id}
DELETE /api/admin/test-cases/{test_case_id}
POST   /api/admin/test-cases/{test_case_id}/run
POST   /api/admin/test-cases/run-batch
GET    /api/admin/test-case-runs
GET    /api/admin/test-case-runs/{run_id}
GET    /api/admin/test-suites
POST   /api/admin/test-suites
POST   /api/admin/test-suites/run-batch
GET    /api/admin/test-suite-runs
GET    /api/admin/test-suite-runs/{suite_run_id}
POST   /api/admin/test-suites/safety-reviewer-smoke/ensure
GET    /api/admin/test-suites/{suite_id}
PATCH  /api/admin/test-suites/{suite_id}
DELETE /api/admin/test-suites/{suite_id}
POST   /api/admin/test-suites/{suite_id}/cases
DELETE /api/admin/test-suites/{suite_id}/cases/{test_case_id}
POST   /api/admin/test-suites/{suite_id}/run
POST   /api/admin/workflow-runs/{run_id}/create-test-case
POST   /api/admin/workflow-runs/{run_id}/replay
```

Typical saved test case call:

```bash
curl -X POST "$API_BASE_URL/api/admin/test-cases" \
  -H "Cookie: $ADMIN_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"name":"Noisy AC intake","endpoint":"cmms-intake","input_text":"Noisy AC in ARC 205","environment_code":"DEFAULT","expected_json":{"validation":{"can_create_work_order":true}},"enabled":true}'
```
