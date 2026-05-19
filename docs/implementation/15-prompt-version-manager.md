# Prompt Version Manager v1

## Purpose

Prompt Version Manager moves endpoint prompts from hardcoded inline strings into SQLite-managed prompt versions. Workflow Run Trace can now record which prompt version, prompt id, model, and temperature were used for a `cmms-intake` run.

This is still a workflow-based AI pipeline with deterministic validation gates. No multi-agent orchestration was added.

## Table

`ai_prompt_versions`

- `id`
- `endpoint`
- `version`
- `name`
- `status`: `draft`, `active`, `archived`
- `system_prompt`
- `user_template`
- `model`
- `temperature`
- `created_at`
- `updated_at`
- `created_by`
- `updated_by`

Each supported endpoint is seeded with a default active `v1` prompt if none exists.

## Supported Endpoints

- `cmms-intake`
- `summarize-work-order`
- `extract-work-order-fields`
- `cmms-assistant`

## Rules

- Only one prompt per endpoint should be active after activation.
- Draft prompts can be edited.
- Archived prompts cannot be edited.
- Active prompt versions are used by API endpoints.
- Admin users can create, edit, test, activate, and archive prompt versions.
- Normal users can see the active prompt version metadata used by Test Console, but not the full prompt text.

## Admin APIs

```text
GET  /api/admin/prompt-versions
GET  /api/admin/prompt-versions/{endpoint}
POST /api/admin/prompt-versions
PATCH /api/admin/prompt-versions/{prompt_id}
POST /api/admin/prompt-versions/{prompt_id}/activate
POST /api/admin/prompt-versions/{prompt_id}/archive
POST /api/admin/prompt-versions/{prompt_id}/test
```

Read-only active metadata:

```text
GET /api/prompt-versions/active/{endpoint}
```

## Workflow Trace Connection

`cmms-intake` records prompt information in the `model_extraction` step:

- `prompt_version`
- `prompt_id`
- `model`
- `temperature`
- `model_call_count`

## Security and Safety

Prompt testing is admin-only. No secrets are stored in prompt text by design. Prompt changes do not bypass output contract validation or environment validation.

No Router Agent, Reviewer Agent, Code Normalization Agent, autonomous planning, CMMS write-back, or email sending was added.

## Future Path

1. Saved test cases
2. Replay workflow run with draft prompt
3. Per-step output contracts
4. Deterministic code normalization improvements
5. Optional LLM code-normalization suggestion step
6. Reviewer step
