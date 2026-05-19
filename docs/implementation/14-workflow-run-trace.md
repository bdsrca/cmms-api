# Workflow Run Trace

## Purpose

Workflow Run Trace adds observability to the current `cmms-intake` pipeline before any future workflow-based multi-agent architecture is introduced.

The product language is intentionally:

```text
Workflow-based AI pipeline with traceable steps.
```

It is not an autonomous multi-agent system.

## Database Tables

Two SQLite tables were added:

- `workflow_runs`
- `workflow_run_steps`

`workflow_runs` stores one row per API workflow execution:

- `run_id`
- `endpoint`
- `environment_code`
- `user_id`
- `api_key_id`
- `source`
- `status`
- `started_at`
- `finished_at`
- `duration_ms`
- `error_message`

`workflow_run_steps` stores the step timeline:

- `step_name`
- `step_order`
- `status`
- `model`
- `prompt_version`
- `duration_ms`
- `input_summary`
- `output_summary`
- `output_json`
- `error_message`

## Traced Steps

The current `cmms-intake` route records:

1. `request_received`
2. `model_extraction`
3. `output_contract_validation`
4. `environment_validation`
5. `response_composed`

Validation steps are deterministic Python rule-engine steps. They are not agents and do not call the model.

## Privacy Note

The trace does not store raw audio, API keys, passwords, or full sensitive request payloads by default.

Request text is reduced to a short redacted summary. Structured output is stored only where useful for debugging contract and validation behavior.

Runtime secrets such as `.env`, `api_keys.json`, `data/*.db`, and `logs/*` must not be included in GitHub repositories, demo zip files, portfolio artifacts, or customer handoff packages. Only `.env.example` should be distributed.

## Retention and Indexes

The local SQLite trace store keeps the latest 1000 workflow runs. Older workflow runs and their steps are removed after a run finishes.

Indexes are created for:

- `workflow_runs.started_at`
- `workflow_runs.endpoint`
- `workflow_runs.environment_code`
- `workflow_run_steps.run_id`

## APIs

Admin-only routes:

```text
GET /api/admin/workflow-runs
GET /api/admin/workflow-runs/{run_id}
```

The normal `cmms-intake` response includes only a trace reference:

```json
{
  "run_id": "run_...",
  "trace": {
    "available": true,
    "run_id": "run_..."
  }
}
```

Full step detail is fetched separately by the portal for admin users.

## Why This Comes Before Multi-Agent

Traceability makes future workflow changes debuggable. Before adding prompt versions, code-normalization suggestions, reviewer steps, or workflow orchestration, the system needs a durable record of what happened at each current step.

## Future Upgrade Path

1. Prompt Version Manager
2. Per-step output contracts
3. Stronger deterministic code normalization
4. Optional LLM code-normalization suggestion step
5. Reviewer Agent
6. Router/classifier only after multiple real workflows exist
