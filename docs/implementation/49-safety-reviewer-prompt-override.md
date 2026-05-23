# Safety Reviewer Prompt Override v1

## Purpose

This pass lets saved test cases and test suites run `cmms-intake` while overriding only the nested `cmms-intake-reviewer` prompt.

The goal is to test reviewer draft prompts from the existing Prompt Versions page without changing the normal API behavior.

## What Changed

- Added optional `reviewer_prompt_id` to test case and test suite run request models.
- Threaded `reviewer_prompt_id` through:
  - test case runner
  - test suite runner
  - `execute_ai_endpoint_for_test`
  - `cmms_intake`
  - `run_safety_reviewer_agent`
- Updated the reviewer smoke suite button in Prompt Versions to pass the selected reviewer prompt id.

## Scope Boundary

Normal `/api/ai/cmms-intake` requests still use the active reviewer prompt. The override is only available through admin test runners.

The primary `prompt_id` still refers to the endpoint being tested. `reviewer_prompt_id` is separate and only applies to the nested Safety Reviewer Agent.

## Safety Boundaries

- No new database tables.
- No new LLM routes.
- No generic chat route.
- No LLM judge.
- No Router Agent or autonomous planning.
- No CMMS write-back, work order creation, approval, or email sending.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_prompt_override tests.test_safety_reviewer_prompt_tuning_ui tests.test_safety_reviewer_suite tests.test_safety_reviewer
```
