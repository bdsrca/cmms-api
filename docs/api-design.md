# API Design

The public showcase uses simple examples, but the production design should be explicit and boring.

## Core endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/ai/intake/text` | Convert typed request text into a validated draft. |
| `POST /api/ai/intake/voice-transcript` | Convert an edited transcript into a validated draft. |
| `POST /api/ai/intake/screenshot` | Convert image-derived content into a validated draft. |
| `POST /api/contracts/validate` | Validate sample model output against a contract. |
| `GET /api/environments/{code}/codes` | Read allowed codes for a scoped environment. |
| `GET /api/usage/summary` | Return safe usage metrics for allowed scopes. |
| `POST /api/tokens/free` | Issue a restricted free token, admin only. |
| `POST /api/tokens/revoke` | Revoke a token, admin only. |

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
