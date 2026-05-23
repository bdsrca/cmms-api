# API Key Scopes v1

## Purpose

Add least-privilege controls for generated API keys without changing the legacy `LLM_API_KEY` compatibility path. Generated keys can now be limited by controlled AI endpoint and environment code.

## Scope Model

Generated API keys support:

- `allowed_endpoints`: controlled AI endpoint slugs such as `cmms-intake`, `summarize-work-order`, `extract-work-order-fields`, `cmms-assistant`, and `intake/email`.
- `allowed_environments`: environment codes such as `DEFAULT` or `TEST`.

Endpoint scopes are validated against the supported endpoint list. Environment scopes are normalized to uppercase. An empty list means unrestricted for that dimension. API keys still only authenticate AI API calls; they do not grant portal admin access.

## Database Changes

The `api_keys` table now includes:

- `allowed_endpoints_json`
- `allowed_environments_json`

Existing databases are migrated with safe `ALTER TABLE` checks during startup.

## Enforcement

`require_api_key` loads the key scopes into request state. AI routes call `enforce_api_key_scope` before invoking LLM or workflow helpers.

The environment check applies when the request includes `environment_code`. Existing bodies that pass explicit `valid_buildings` and `valid_priorities` continue to work.

## UI

The API Keys admin page now includes fields for allowed endpoints and allowed environments when generating a key. Generated keys are still shown only once.

## Security Notes

- Plaintext API keys are never stored.
- Scope lists are not secrets and are safe to display to admins.
- `LLM_API_KEY` remains an AI-endpoint compatibility key only; it does not create an admin portal session.
- Admin routes remain protected by portal session role checks.

## Validation

Targeted tests cover:

- schema migration columns
- create/list/patch scope serialization
- helper-level endpoint and environment blocking
- route-level endpoint and environment blocking
- legacy `LLM_API_KEY` AI endpoint compatibility
