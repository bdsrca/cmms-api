# Test Console Workflow Bench v1

## Purpose

Make the Test Console clearer now that the portal supports CMMS intake, email intake, orchestration preview, assistant, extraction, and summarization modes.

## Changes

- Kept one simple Test Console page instead of adding new top-level pages.
- Added lightweight mode-specific UI behavior:
  - Email Intake shows From, To, and Subject fields.
  - Email body continues to use the main request textarea.
  - Orchestration Preview uses the existing CMMS intake endpoint in full workflow mode.
  - Non-workflow modes hide the workflow selector.
  - Primary run button text changes by mode.
- Email Intake mode now uses the visible email fields in the request body.

## Safety

- No new backend route was added.
- No generic chat endpoint was added.
- No backend audio upload was added.
- No LLM judge or autonomous router was added.
- CMMS write-back behavior was not changed.
- Email sending behavior was not added.

## Verification

- Added UI source tests for mode-specific controls and routing.
- Existing endpoint routing remains pointed at controlled API paths only.
