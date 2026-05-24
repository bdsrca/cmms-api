# Controlled Work Order Creation And Assignment Implementation Plan

> REQUIRED SUB-SKILLS: Use `superpowers:test-driven-development` for each task and `superpowers:verification-before-completion` before claiming completion.

## Goal

Implement Project 2 from the CMMS agentic action roadmap: produce a deterministic action plan for controlled work-order creation and assignment to an on-duty technician, while preserving the existing CMMS connector safety gates.

## Scope

This phase implements assignment as fields included in the controlled work-order create payload. A future phase can add a separate assignment connector action if a target CMMS requires create and assign to be separate API calls.

## Task 1: On-Duty Technician Resolver

**Files:**
- Create: `app/technician_roster.py`
- Modify: `app/config.py`
- Test: `tests/test_technician_roster.py`

- [x] Write failing tests for exact night-shift technician resolution, ambiguous matching, not configured, and no assignment intent.
- [x] Add `technician_roster` as an importable environment code category.
- [x] Resolve technician rows from `code_values` metadata with shift, trade eligibility, assign-to code, issue-to code, and job type.
- [x] Return `cmms_assignment_context_v1`.
- [x] Run `python -m unittest tests.test_technician_roster -v`.

## Task 2: Deterministic Action Plan

**Files:**
- Create: `app/cmms_action_plan.py`
- Test: `tests/test_cmms_action_plan.py`

- [x] Write failing tests for initial planned actions and final post-push statuses.
- [x] Build `cmms_action_plan_v1` with `create_work_order` and `assign_work_order` actions.
- [x] Include stable idempotency keys per action.
- [x] Reflect `sent`, `dry_run`, `blocked`, `skipped`, and `failed` CMMS push results without inventing success.
- [x] Run `python -m unittest tests.test_cmms_action_plan -v`.

## Task 3: Intake Integration

**Files:**
- Modify: `app/ai_endpoints.py`
- Modify: `app/models.py`
- Modify: `app/config.py`
- Modify: `app/output_contracts.py`
- Test: `tests/test_controlled_assignment_intake_api.py`

- [x] Write failing API tests proving `assignment_context` and `action_plan` appear in `cmms-intake`.
- [x] Insert `assignment_resolution` and `action_plan_composed` workflow trace steps before output contract validation.
- [x] Apply resolved assignment fields to the output-contract payload before environment validation and CMMS handoff.
- [x] Include an idempotency key in CMMS connector calls.
- [x] Keep draft text advisory-only.
- [x] Run `python -m unittest tests.test_controlled_assignment_intake_api -v`.

## Task 4: Connector Idempotency And Related Regression

**Files:**
- Modify: `app/cmms_connectors.py`
- Modify: `tests/test_cmms_intake_auto_push.py`
- Test: `tests/test_cmms_intake_auto_push.py`

- [x] Write failing tests proving the connector receives `Idempotency-Key`.
- [x] Add the idempotency header when push context provides an idempotency key.
- [x] Return the key in `cmms_push`.
- [x] Run existing connector and handoff tests.

## Final Verification

- [x] Run focused phase 2 tests.
- [x] Run existing intake, handoff, auto-push, and asset-aware tests.
- [x] Run `python -m unittest discover -s tests`.
- [x] Run compile check for touched Python files.
