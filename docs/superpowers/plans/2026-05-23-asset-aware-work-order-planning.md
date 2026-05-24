# Asset-Aware Work Order Planning Implementation Plan

> REQUIRED SUB-SKILLS: Use `superpowers:test-driven-development` for each task and `superpowers:verification-before-completion` before claiming completion.

## Goal

Implement Project 1 from the CMMS agentic action roadmap: enhance `cmms-intake` with deterministic asset-aware planning while keeping external actions advisory and gated exactly as they are today.

## Task 1: Asset Registry Resolver

**Files:**
- Create: `app/asset_registry.py`
- Test: `tests/test_asset_registry.py`

- [x] Write failing tests for exact asset match, ambiguous match, missing environment, and no configured assets.
- [x] Implement a small resolver that reads enabled `code_values` rows from category `assets`.
- [x] Parse `aliases` and `metadata_json` into normalized candidate objects.
- [x] Return `cmms_asset_context_v1` with `resolved`, `ambiguous`, `not_found`, `not_configured`, or `skipped` status.
- [x] Run `python -m unittest tests.test_asset_registry -v`.

## Task 2: Intake Asset Context and Planning

**Files:**
- Modify: `app/ai_endpoints.py`
- Modify: `app/models.py`
- Test: `tests/test_asset_aware_intake_api.py`

- [x] Write failing API tests proving `asset_context` and `work_order_plan` appear in `cmms-intake`.
- [x] Insert `asset_resolution` and `work_order_planning` workflow trace steps after model extraction and before output contract validation.
- [x] Include asset context and planning hints in draft-generation context.
- [x] Keep CMMS write behavior unchanged.
- [x] Run `python -m unittest tests.test_asset_aware_intake_api -v`.

## Task 3: Environment Category and Contract Compatibility

**Files:**
- Modify: `app/config.py`
- Modify: `app/output_contracts.py`
- Modify: `app/intake_handoff.py`
- Test: `tests/test_asset_aware_contract_and_handoff.py`

- [x] Add `assets` as an importable environment code category.
- [x] Allow `asset_context` and `work_order_plan` in the default intake output contract.
- [x] Carry resolved asset context into canonical CMMS payload preview as advisory metadata.
- [x] Run `python -m unittest tests.test_asset_aware_contract_and_handoff -v`.

## Final Verification

- [x] Run focused asset-aware tests.
- [x] Run existing related intake/handoff/connector tests.
- [x] Run compile check for touched Python files.
