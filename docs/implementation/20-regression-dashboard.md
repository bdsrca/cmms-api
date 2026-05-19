# Regression Dashboard

## Purpose

Regression Dashboard v1 is a read-only operational view for local CMMS AI regression health. It summarizes whether required suites are ready, whether prompt comparisons are regressing, whether promotions were overridden, and where validation failures are clustering.

It is visibility only. It does not change prompts, run agents, write to CMMS, or send notifications.

## Data Sources

The dashboard reads existing tables:

- `ai_test_suites`
- `ai_test_suite_runs`
- `ai_test_suite_run_cases`
- `ai_test_case_runs`
- `ai_prompt_comparisons`
- `ai_prompt_comparison_cases`
- `ai_prompt_promotions`
- `workflow_runs`
- `workflow_run_steps`

No new primary business table is required for v1.

## Dashboard Sections

- Required Suite Readiness
- Latest Suite Runs
- Recent Prompt Comparisons
- Recent Prompt Promotions
- Workflow Summary
- Top Failing Fields
- Recent Validation Failures

The UI uses cards and tables instead of heavy charts.

## Required Suite Readiness Logic

For every enabled suite marked `required_for_promotion`:

- no latest run: `not_run`
- latest run passed: `passed`
- latest run warning/failed/error: shown as warning or failed

Each item includes suite name, endpoint, environment, latest prompt version, last run time, pass rate, status, and suite run id when available.

## Top Failing Fields Limitation

Field counts are best-effort. They are gathered from recent saved test case run comparison JSON and environment validation errors/warnings inside actual response JSON.

This is intentionally conservative and not a full diff engine.

## Security Notes

The dashboard API is admin-only:

```text
GET /api/admin/regression-dashboard
```

Normal users cannot access detailed regression data in v1.

## No LLM Judge

No LLM judge, multi-agent router, reviewer agent, code normalization agent, CMMS write-back, or email sending was added.

## Future Upgrade Path

- trend charts
- release readiness score
- endpoint-specific health dashboards
- environment-specific regression views
- alerting after explicit email/notification design
