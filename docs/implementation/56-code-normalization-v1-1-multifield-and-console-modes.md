# Code Normalization v1.1 Multifield Candidate Collection

## Purpose

This pass extends the code-normalization suggestion path beyond priority so supported CMMS code fields can be suggested and deterministically accepted when values are not already valid configured codes.

## What Changed

- Added `collect_invalid_code_candidates()` in `app/code_normalizer.py`.
- Candidate collection now checks configured code, label, and aliases before asking the normalizer for suggestions.
- The `cmms-intake` workflow collects invalid candidates after output contract validation and before the code-normalization suggestion agent runs.
- Supported candidate fields are:
  - `priority`
  - `work_order_type`
  - `job_type`
  - `assign_to`
  - `issue_to`
- Test Console mode options now include:
  - `Email Intake`, routed to the existing `/api/ai/intake/email` endpoint.
  - `Orchestration Preview`, routed to the existing `/api/ai/cmms-intake` endpoint in full workflow mode.

## Safety Boundary

The normalizer still only suggests values. Python applies suggestions only when the suggested code exists in the enabled code list supplied for the environment. No CMMS write-back, email sending, generic chat route, LLM judge, or autonomous routing was added.

## Notes

`Orchestration Preview` is not a new endpoint. It is a Test Console convenience mode for the existing controlled intake pipeline so operators can see orchestration, assignment, inventory, action plan, validation, reviewer, and gate output from one run.

## Verification Scope

- Pure function tests cover candidate detection and code/label/alias matches.
- Intake API tests cover normalization of an invalid `work_order_type`.
- UI tests cover Test Console mode options and route mapping.
