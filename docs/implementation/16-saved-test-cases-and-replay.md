# Saved Test Cases and Replay

## Purpose

Saved test cases add a regression harness for the local CMMS AI endpoints. They make prompt, output contract, validation rule, and code-list changes testable instead of relying on subjective one-off console checks.

This is not a multi-agent feature. It reuses the existing controlled endpoint pipelines and records normal workflow traces when a test case is executed.

## Database Tables

`ai_test_cases` stores admin-saved examples:

- `name`
- `endpoint`
- `environment_code`
- `input_text`
- `source`
- `expected_json`
- `enabled`
- `tags`
- `notes`
- audit timestamps and user ids

`ai_test_case_runs` stores each execution:

- linked `test_case_id`
- linked workflow `run_id` when available
- endpoint, environment, prompt id/version
- status, duration, actual response JSON, comparison JSON, and error message

Indexes are added for endpoint, environment, enabled state, run status, test case id, and started timestamp.

## Expected JSON Format

Version 1 supports simple assertions only:

```json
{
  "summary_contains": ["water leak"],
  "building": "ARC",
  "room": "205",
  "priority": "URGENT",
  "work_order_type": "PLUMBING",
  "contract_valid": true,
  "environment_valid": false,
  "expected_errors": ["priority"],
  "expected_warnings": []
}
```

There is no JSONPath or complex assertion DSL in v1.

## Comparison Behavior

The comparison helper checks:

- direct equality for result fields: building, room, priority, work order type, assign to, issue to, and job type
- summary substring matches
- contract validation pass/fail
- environment validation pass/fail
- expected error field names
- expected warning field names

The result is stored as comparison JSON with pass/fail detail for later review.

## Replay Limitation

Workflow replay only works when the original input text is intentionally available from a saved test case run. Normal workflow traces do not store full request text by default, so those runs fail safely with a clear message.

This keeps trace storage useful without turning it into a raw request archive.

## Security and Privacy Notes

The feature does not store:

- API keys
- authorization headers
- cookies
- passwords
- session tokens
- raw audio

`input_text` is stored only when an admin explicitly saves it as a test case.

## Future Upgrade Path

- richer assertion DSL
- test suites
- prompt A/B comparison reports
- regression dashboard
- deterministic normalization comparison
- reviewer step
- workflow-based multi-agent orchestration after regression safety exists
