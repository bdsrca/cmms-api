# Safety Reviewer Visibility v1

## Purpose

This pass makes the Safety Reviewer Agent visible and testable at a basic level.

The reviewer already runs inside `cmms-intake`. This update adds a simple Test Console panel and saved-test-case assertions so operators can see and regression-test reviewer output.

## Scope

- Added a Safety Review panel to the Test Console response surface.
- Added `renderSafetyReview(review)` in the portal UI.
- Wired normal test runs, email intake runs, and matching saved test-case runs to render the review block.
- Added reviewer fields to the default "Save as Test Case" expected JSON.
- Added deterministic comparison support for:
  - `review_status`
  - `review_human_review_recommended`
  - `review_risk_flags_contains`

## Out of Scope

- No new agent was added.
- No LLM judge was added.
- No autonomous routing or planning was added.
- No CMMS write-back, work order creation, or email sending was added.

## Notes

The Safety Review panel is advisory-only. It does not alter contract validation, environment validation, readiness, normalized values, drafts, or handoff candidates.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_safety_reviewer tests.test_safety_reviewer_ui
```
