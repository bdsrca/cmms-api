# Prompt Promotion Gate

## Purpose

Prompt Promotion Gate v1 prevents unsafe prompt activation by requiring deterministic regression evidence before a draft prompt becomes active.

The gate uses existing saved test cases and Prompt A/B Comparison results. It does not use an LLM judge.

## Database Table

`ai_prompt_promotions` stores the promotion audit trail:

- `promotion_id`
- `endpoint`
- `previous_prompt_id`
- `promoted_prompt_id`
- `comparison_id`
- `gate_status`
- `override_used`
- `override_reason`
- `promoted_by`
- `promoted_at`
- `summary_json`

Indexes support filtering by endpoint, promoted time, promoted prompt, and comparison id.

## Gate Rules

The promotion check blocks activation unless:

- the candidate prompt exists
- the candidate is draft or already active
- the candidate is not archived
- a completed comparison id is supplied
- the comparison endpoint matches the candidate endpoint
- the comparison baseline is the current active prompt
- the comparison candidate is the prompt being promoted
- the comparison has `regressed == 0`
- the comparison has `error == 0`
- `candidate_passed >= baseline_passed`

The API returns blocking reasons so admins can see exactly why promotion is not allowed.

New prompt versions must be created as drafts. Direct creation as `active` is blocked so activation cannot bypass the promotion gate.

## Override Behavior

Admins may override a blocked gate only by supplying a non-empty override reason.

Override activation:

- activates the prompt
- archives the previous active prompt for the endpoint
- records `gate_status = overridden`
- records `override_used = 1`
- stores the override reason

Archived prompts cannot be activated.

## Audit Trail

Every successful activation through the gate writes a promotion row, whether the gate passed or was overridden. This creates a local audit trail for prompt changes.

## UI Behavior

Prompt Versions now includes:

- Promotion Readiness panel in prompt detail
- Check Promotion Gate
- Activate Prompt
- Override and Activate
- Prompt comparison action: Use This Comparison for Promotion
- Promotion History table

## No LLM Judge

This feature does not add an LLM judge, multi-agent logic, reviewer agent, router agent, code normalization agent, CMMS write-back, or email sending.

## Future Upgrade Path

- test suites
- required suite thresholds
- approval workflow
- prompt promotion policy by endpoint
- prompt promotion policy by environment
