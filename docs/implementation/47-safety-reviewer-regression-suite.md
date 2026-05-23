# Safety Reviewer Regression Suite v1

## Purpose

This pass adds a minimal regression-suite framework for the Safety Reviewer Agent.

The goal is to let an admin create a reusable saved test suite for reviewer behavior without adding new database tables, new agents, or new LLM routes.

## What Changed

- Added `safety_reviewer_smoke_definitions(...)` in `app/test_suites.py`.
- Added `ensure_safety_reviewer_smoke_suite(...)` to create or refresh the recommended suite.
- Added admin route:

```text
POST /api/admin/test-suites/safety-reviewer-smoke/ensure
```

- Added a Test Suites page button:

```text
Safety Reviewer Smoke Suite
```

## Suite Contents

The suite is named:

```text
Safety Reviewer Smoke Suite
```

It uses endpoint:

```text
cmms-intake
```

The first stable case is enabled by default:

- normal HVAC request
- expected reviewer status: `pass`
- expected `review_human_review_recommended`: `false`

Two warning-oriented cases are created as disabled templates:

- missing location warning template
- urgent leak warning template

These are disabled by default so the suite does not become noisy before the local reviewer prompt behavior is tuned.

## Promotion Behavior

The suite is not marked `required_for_promotion` by default. Admins can enable that later from the Test Suites editor after confirming the suite is stable for their local model and prompts.

## Safety Boundaries

- No new agent was added.
- No LLM judge was added.
- No Router Agent or autonomous planning was added.
- No CMMS write-back, work order creation, approval, or email sending was added.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_suite tests.test_safety_reviewer tests.test_safety_reviewer_ui
```
