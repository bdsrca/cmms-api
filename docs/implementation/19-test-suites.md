# Test Suites

## Purpose

Test Suites v1 groups saved CMMS AI test cases into reusable regression suites. Suites let admins evaluate prompt changes, validation changes, and promotion readiness with suite-level pass/fail rules.

This is deterministic regression infrastructure. It does not add an LLM judge or multi-agent behavior.

## Database Tables

`ai_test_suites` stores suite metadata:

- suite id, name, endpoint, environment
- enabled state
- required-for-promotion flag
- minimum pass rate
- zero-error and zero-regression policy flags
- tags, description, timestamps, and audit users

`ai_test_suite_cases` stores suite membership:

- suite id
- test case id
- sort order
- enabled state

`ai_test_suite_runs` stores each suite execution:

- suite run id
- suite id
- endpoint and environment
- prompt id/version
- status, timing, summary JSON, and creator

`ai_test_suite_run_cases` stores per-case suite execution results:

- suite run id
- test case id
- linked test case run id
- status
- comparison JSON

## Suite Run Behavior

When a suite runs:

1. Enabled suite cases are loaded in order.
2. Each test case runs through the existing saved test case runner.
3. Each test case still creates normal workflow traces through the existing endpoint pipeline.
4. The suite stores a summary with total, passed, failed, warning, error, pass rate, threshold checks, and final status.

Pass rate is calculated from strictly `passed` cases divided by total cases. Warnings remain visible and produce a suite warning status when the pass rate still meets the configured threshold.

## Required Suite Promotion Readiness

Prompt Promotion Gate v1 now includes optional required suite readiness.

If no required suites exist for the endpoint/environment, the existing A/B comparison gate behavior remains unchanged.

If required suites exist, promotion-check includes:

```json
{
  "required_suites_found": true,
  "required_suites_passed": false,
  "suite_failures": []
}
```

Promotion is blocked when a required suite has no latest run for the candidate prompt or when its latest run failed/error.

Admins can still use the existing override flow with a recorded reason.

## Security Notes

Suite APIs are admin-only in v1.

Suites do not store API keys, cookies, passwords, session tokens, or raw audio. They reference saved test cases, which only store input text when an admin explicitly saves it for regression testing.

## No LLM Judge

Suite pass/fail behavior is based on existing saved expectations, output contracts, environment validation, and deterministic comparison logic.

No LLM judge, router agent, reviewer agent, code normalization agent, CMMS write-back, or email sending was added.

## Future Upgrade Path

- regression dashboard
- suite trend history
- endpoint-specific promotion policies
- environment-specific release gates
- reviewer step only after suite-level regression safety exists
