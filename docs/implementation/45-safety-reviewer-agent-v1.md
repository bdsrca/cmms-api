# Safety Reviewer Agent v1

## Purpose

This pass adds the first lightweight workflow-agent framework slice: an advisory Safety Reviewer Agent inside the existing `cmms-intake` pipeline.

The reviewer runs after output contract validation and environment validation. It reviews the already-composed result, validation blocks, and draft text for safety issues such as over-promising, missing review warnings, or language that implies CMMS write-back occurred.

## Scope

- Added `app/safety_reviewer.py` for reviewer normalization, prompt execution, and skipped/failed review blocks.
- Added the `cmms-intake-reviewer` prompt endpoint and default active prompt seed.
- Added a `safety_reviewer_agent` workflow trace step.
- Added a `review` block to `cmms-intake` responses.
- Added focused unit/API tests for reviewer behavior.

## Response Block

The reviewer returns a stable advisory block:

```json
{
  "status": "pass",
  "risk_flags": [],
  "review_warnings": [],
  "human_review_recommended": false,
  "notes": [],
  "source": "safety_reviewer_agent"
}
```

Allowed statuses are `pass`, `warning`, `fail`, and `skipped`.

## Safety Boundary

The reviewer does not change extracted fields, normalized codes, deterministic validation, drafts, or CMMS action state. It is advisory only and cannot create work orders, write to CMMS, approve requests, or send emails.

If output contract validation fails, the reviewer is skipped because the model output shape is not reliable enough to review.

## Future Work

- Add a small UI panel in Test Console for the reviewer block.
- Add saved test cases for reviewer warnings.
- Consider later reviewer-specific output contracts if the step becomes more complex.

## Verification

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer tests.test_safety_reviewer_intake_api
```
