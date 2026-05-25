# Code Normalization Suggestion Agent v1 Closeout

## Purpose

This closeout finishes the first bounded code-normalization agent slice for the controlled CMMS intake workflow. The agent suggests configured CMMS codes, while deterministic Python code accepts, rejects, and exposes every decision.

## What Changed

- Added a Test Console and Email Intake panel for `code_normalization`.
- Kept accepted and rejected suggestions visible outside the raw JSON block.
- Passed a redacted request summary into the normalizer prompt context instead of the full raw request text.
- Preserved `raw_extracted_fields`, `validated_fields`, and `invalid_code_candidates` so fallback defaults do not hide values that need normalization.
- Cleaned up the code-normalizer API tests so monkeypatched Ollama callers are restored after each test.

## Workflow Order

The `cmms-intake` full workflow now keeps this order:

1. Model extraction
2. Output contract validation
3. Code normalization suggestion agent
4. Environment validation
5. Draft generation
6. Safety reviewer
7. CMMS auto-push gate
8. Response composition

## Safety Notes

- The normalizer does not write to CMMS.
- The normalizer does not create work orders.
- The normalizer does not send email.
- Suggested codes are accepted only when they are configured and enabled for the selected environment.
- Low-confidence suggestions and suggestions for already-valid fields are rejected and shown.
- Trace output stores summary counts and rejection reason codes, not full prompt contents or secrets.

## Verification

Focused tests cover:

- `issue_to` default validation rule category mapping.
- Raw invalid priority preservation.
- Pure normalizer context/output/apply behavior.
- `cmms-code-normalizer` prompt seeding.
- Intake response exposure of `code_normalization`.
- Normalizer trace ordering.
- Test Console rendering of the code normalization panel.

## Remaining Work

- Extend invalid candidate collection beyond `priority` for `work_order_type`, `job_type`, `assign_to`, and `issue_to`.
- Add saved regression test cases for multilingual urgent phrases and configured employee/code aliases.
- Consider a stricter redaction helper shared across trace and prompt-context construction.
