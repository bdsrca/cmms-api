# Prompt A/B Comparison

## Purpose

Prompt A/B Comparison lets admins compare a baseline prompt version against a candidate prompt version using saved CMMS regression test cases.

The feature answers a practical question: did the candidate prompt improve, regress, or leave deterministic test results unchanged?

## Database Tables

`ai_prompt_comparisons` stores one comparison run:

- `comparison_id`
- `endpoint`
- `environment_code`
- `baseline_prompt_id`
- `candidate_prompt_id`
- status and timing
- summary JSON
- creator

`ai_prompt_comparison_cases` stores per-test-case results:

- linked comparison id
- linked test case id
- baseline and candidate workflow run ids
- baseline and candidate statuses
- deterministic result classification
- case comparison JSON

Indexes support filtering by endpoint, status, started time, comparison id, test case id, and case result.

## Classification

The comparison is deterministic:

- baseline failed and candidate passed: `improved`
- baseline passed and candidate failed: `regressed`
- both passed: `unchanged_pass`
- both failed: `unchanged_fail`
- any run error: `error`

Statuses `passed` and `warning` are treated as passing for prompt comparison, because warning still means the saved assertions passed.

## Deterministic Behavior

Each matching saved test case is run twice:

1. once with the baseline prompt id
2. once with the candidate prompt id

The existing saved test case comparison logic evaluates each run. The A/B comparison only compares the deterministic run statuses and a small set of output fields.

Simple field differences are captured for:

- summary
- building
- room
- priority
- work order type
- assign to
- issue to
- job type
- contract validation status
- environment validation status

## No LLM Judge

This feature does not use an LLM judge. It does not add agents, reviewer steps, router logic, or autonomous planning.

The result is intentionally based on saved expectations, output contracts, environment validation, and deterministic comparison code.

## UI Behavior

Prompt Versions includes:

- Compare Against Active
- Compare Against Another Prompt
- Prompt Comparisons list
- Comparison Detail with summary cards and case-level table
- Trace links for baseline and candidate workflow runs

## Future Upgrade Path

- test suites
- trend dashboard
- prompt promotion gate
- richer field diffs
- reviewer step after regression safety exists
- workflow-based multi-agent only after deterministic regression safety is mature
