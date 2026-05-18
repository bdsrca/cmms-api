# 11 - Output Contract Schema Manager

The Output Contract layer validates response shape before environment business validation.

Pipeline order:

1. Model raw output
2. JSON parsing
3. Output contract validation
4. Environment validation
5. Stable API response

The default `cmms-intake` contract requires `summary`, defines allowed fields, and uses strict mode so extra fields fail validation.

Contract validation is endpoint-level, not environment-level. Environment Validation Rules still handle business correctness such as code-list membership.

Implemented APIs:

- `GET /api/output-contracts/{endpoint}`
- `GET /api/admin/output-contracts`
- `GET /api/admin/output-contracts/{endpoint}`
- `POST /api/admin/output-contracts`
- `PATCH /api/admin/output-contracts/{contract_id}`
- `POST /api/admin/output-contracts/{contract_id}/activate`
- `POST /api/admin/output-contracts/{contract_id}/validate-sample`

Rules:

- Only one active contract per endpoint.
- Admin users can create, update, activate, and archive contracts.
- Normal users cannot edit contracts.
- Raw model output is not exposed by default.
- If contract validation fails, environment validation is skipped and marked `not_run`.

The v1 validator intentionally supports a focused JSON Schema subset:

- `type`
- `required`
- `properties`
- `additionalProperties`

This covers the initial API contract without adding a heavy dependency.
