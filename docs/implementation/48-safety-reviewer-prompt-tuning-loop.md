# Safety Reviewer Prompt Tuning Loop v1

## Purpose

This pass adds a basic shortcut from the Prompt Versions page to the Safety Reviewer Smoke Suite.

The goal is to make the reviewer prompt tuning loop easier to find:

```text
Prompt Versions -> cmms-intake-reviewer -> Create/Run Safety Reviewer Smoke Suite
```

## What Changed

- Added a `Safety Reviewer Smoke Suite` panel on `cmms-intake-reviewer` prompt details.
- Added a `Create / Refresh Smoke Suite` button.
- Added a `Run Safety Reviewer Smoke Suite` button.
- Results are written to the existing prompt result output panel.
- The panel shows the latest suite run status and pass rate after running.

## Original Limitation

This basic pass uses the existing test suite runner. It runs the current active intake workflow and active reviewer prompt.

It does not pass a draft `cmms-intake-reviewer` prompt id into the nested reviewer step. Draft reviewer prompt override is intentionally deferred to avoid changing runner semantics in this small UI pass.

This limitation was addressed in `49-safety-reviewer-prompt-override.md`.

## Safety Boundaries

- No new tables.
- No new LLM routes.
- No new agent.
- No LLM judge.
- No CMMS write-back, work order creation, approval, or email sending.

## Future Work

- Add explicit reviewer prompt override support for suite runs.
- Add reviewer prompt A/B comparison once override wiring is stable.
- Add promotion gate awareness for reviewer-specific required suites.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_prompt_tuning_ui tests.test_safety_reviewer_suite tests.test_safety_reviewer_ui
```
