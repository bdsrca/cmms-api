# Safety Reviewer Prompt Compare Preview v1

## Purpose

This pass adds a lightweight comparison preview for `cmms-intake-reviewer` prompts.

It lets an admin compare the active reviewer prompt against the currently selected reviewer prompt using the existing Safety Reviewer Smoke Suite.

## What Changed

- Added `Compare Active vs This Prompt` to the `cmms-intake-reviewer` prompt detail panel.
- The UI now:
  - ensures the Safety Reviewer Smoke Suite exists
  - runs the suite once with the active reviewer prompt
  - runs the suite once with the selected reviewer prompt
  - renders a deterministic summary in the existing prompt result panel

## Persistence

This is a preview-only comparison. It does not create a new prompt comparison table row.

The individual suite runs are still stored by the existing test suite runner, so admins can inspect suite run history if needed.

## Classification

The preview marks a regression when:

- candidate errors are greater than baseline errors
- candidate passed count is lower than baseline passed count

It marks improvement when the opposite is true.

## Safety Boundaries

- No new database tables.
- No new LLM routes.
- No new agent.
- No LLM judge.
- No autonomous planning.
- No CMMS write-back, work order creation, approval, or email sending.

## Future Work

- Persist reviewer prompt comparisons if this preview proves useful.
- Add reviewer-specific promotion gate checks.
- Add richer per-case diffs for reviewer fields.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer_prompt_compare_ui tests.test_safety_reviewer_prompt_tuning_ui tests.test_safety_reviewer_prompt_override
```
