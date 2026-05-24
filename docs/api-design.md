# API Design

The public showcase uses simple examples, but the production design should be explicit and boring.

For copyable Postman-style requests, see [`api-sample-calls.md`](api-sample-calls.md).

## Core endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/ai/cmms-intake` | Convert typed request text into a validated advisory draft. |
| `POST /api/ai/intake/email` | Convert email fields into the same controlled intake workflow. |
| `POST /api/ai/cmms-assistant` | Return a controlled advisory CMMS assistant response. |
| `POST /api/ai/extract-work-order-fields` | Extract work-order fields without creating a work order. |
| `POST /api/ai/summarize-work-order` | Return a short work-order summary. |
| `GET /api/environments` | List configured environments for the current portal user. |
| `GET /api/environments/{code}/validation-rules` | Read validation rules for a scoped environment. |
| `POST /api/environments/{code}/validate-sample` | Validate a sample payload against environment rules. |
| `GET /api/output-contracts/{endpoint}` | Read the active output contract for an endpoint. |

## Response pattern

A useful response should contain:

- `request_id`;
- `draft`;
- `normalized_fields`;
- `contract_validation`;
- `environment_validation`;
- `warnings`;
- `errors`;
- `confidence`;
- `next_action`;
- `audit_reference`.

## Next action values

Good values:

- `review_before_cmms_write`;
- `ask_for_more_information`;
- `blocked_by_validation`;
- `blocked_by_token_scope`;
- `ready_for_supervisor_review`;
- `draft_only_demo_result`.

The API should avoid returning `created_work_order` unless a separate controlled write-back gate has actually run.
