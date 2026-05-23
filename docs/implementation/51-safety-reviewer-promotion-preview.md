# Safety Reviewer Promotion Preview

## Purpose

This step adds a small promotion helper for the `cmms-intake-reviewer` prompt detail page.

Reviewer prompt comparisons are currently preview-only and are run through the existing Safety Reviewer Smoke Suite. Because they are not persisted as normal Prompt A/B Comparison records, the existing Prompt Promotion Gate remains unchanged and still requires either a normal comparison or an explicit admin override.

## UI Behavior

The Safety Reviewer Smoke Suite panel now includes a Promotion Preview area.

After an admin runs **Compare Active vs This Prompt**:

- The active reviewer prompt is run against the smoke suite.
- The selected reviewer prompt is run against the same suite using `reviewer_prompt_id`.
- The UI compares pass/error counts deterministically.
- If no regression is found, the UI offers **Use Preview as Override Reason**.
- The button pre-fills the existing Promotion Readiness override reason field with the baseline and candidate suite run ids.

The admin still has to click **Override and Activate**. The override is recorded by the existing prompt promotion audit trail.

## Safety Boundary

No backend promotion gate rule was loosened.

No new reviewer promotion route was added.

No LLM judge was added.

No multi-agent orchestration was added.

The preview is only an operator convenience for documenting why an explicit override is being used in v1.

## Future Upgrade Path

- Persist reviewer prompt comparisons in a first-class comparison table.
- Allow the promotion gate to accept persisted reviewer prompt comparison ids.
- Replace override-based reviewer activation with a dedicated reviewer prompt promotion policy.
- Add required reviewer-specific suites once the reviewer regression surface is stable.
