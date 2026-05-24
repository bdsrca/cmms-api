# CMMS Agentic Action Roadmap Design

## Goal

Turn the current local CMMS AI API from a validated advisory intake system into a controlled multi-step action system that can eventually handle:

> Help me create a high-priority work order for AHU-3, assign it to tonight's on-duty technician, check whether filters are in stock, generate a purchase request if not, and clearly explain the reason.

The design keeps the existing safety boundary: LLMs may classify, extract, suggest, review, and draft, but external system writes must pass deterministic server-side gates, scoped permissions, connector policy, audit logging, and human-review requirements where configured.

## Current Baseline

Already present:

- Controlled `cmms-intake` workflow for advisory work-order drafts.
- Deterministic validation rules for request type, location, priority, missing fields, review requirements, and advisory state.
- Output contracts before business validation.
- Workflow run trace with step-level metadata.
- Safety Reviewer Agent.
- Prompt versions, comparisons, promotion gate, saved test cases, test suites, and regression dashboard.
- Canonical CMMS payload preview, environment handoff preview, connector configuration, and gated CMMS auto-push foundation.

Still missing for the target user request:

- Asset lookup for `AHU-3` and related CMMS asset metadata.
- Asset-to-parts/BOM mapping for filters and required quantities.
- Technician roster or on-call schedule lookup.
- Inventory lookup connector.
- Purchase request connector.
- Multi-action orchestration with idempotency, retries, partial failure handling, and audit evidence.
- Action-specific permission scopes and approval policy.

## Project Split

Use three large projects, each valuable on its own and each building on the existing validation, workflow trace, prompt promotion, and test suite infrastructure.

## Project 1: Asset-Aware Advisory Work Order Planning

### Outcome

The system can understand requests like `AHU-3 needs filters` as an asset-aware work-order candidate, but still remains advisory-only.

After this project, the target request can produce:

- A validated work-order draft for `AHU-3`.
- A resolved or ambiguous CMMS asset candidate.
- Suggested work type, trade, priority, and likely parts.
- A transparent reason block explaining what was inferred and what remains unverified.
- Workflow trace steps for asset resolution and planning.

It must not create a work order, assign a technician, reserve inventory, or create a purchase request.

### Agents and Deterministic Components

- Existing Intake Agent extracts the user's intent.
- Asset Resolution Agent suggests asset candidates from deterministic lookup results.
- Parts Planning Agent suggests likely required parts from asset type and BOM context.
- Policy Agent or deterministic policy layer marks which actions are advisory-only.
- Safety Reviewer Agent confirms the response does not claim writes happened.

### Data and Connectors

- Add an asset registry abstraction.
- Add environment-specific asset code normalization.
- Add optional asset BOM or asset-type parts mapping.
- Keep external lookup read-only.

### API Shape

- Extend intake response with `asset_context`.
- Extend canonical payload preview with `asset`.
- Extend workflow trace with `asset_resolution` and `work_order_planning` steps.
- Add admin-managed test cases for asset resolution examples.

### Safety Gates

- Low-confidence asset matches must require review.
- Ambiguous asset names must not auto-select silently.
- Suggested parts must be marked as planning hints unless backed by a configured BOM.
- Prompt output must be contract-validated before use.

### Tests

- Asset exact match: `AHU-3` resolves to one configured asset.
- Asset ambiguous match: multiple AHU records require review.
- Unknown asset: no write-ready handoff.
- Parts hint without BOM remains advisory.
- Safety reviewer rejects text that claims a work order or purchase request was created.

### Skill Usage

- `superpowers:brainstorming` for refining asset and BOM requirements.
- `superpowers:writing-plans` before implementation.
- `superpowers:test-driven-development` for each new resolver and API contract.
- `superpowers:systematic-debugging` for failed lookup or validation behavior.
- `superpowers:verification-before-completion` before declaring the project complete.

## Project 2: Controlled Work Order Creation and Assignment

### Outcome

The system can create a CMMS work order and assign it only when all deterministic gates pass and the configured environment allows it.

After this project, the target request can produce:

- A real CMMS work order when auto-push is explicitly enabled.
- Assignment to tonight's on-duty technician when the roster lookup is configured and unambiguous.
- A clear response that distinguishes created, assigned, pending review, blocked, or failed states.
- A durable audit trail for request, validation, safety review, handoff readiness, connector response, and assignment decision.

### Agents and Deterministic Components

- Scheduling Agent suggests shift, queue, and eligible technician from roster data.
- Policy layer decides whether assignment may be automatic.
- Existing Safety Reviewer Agent checks final wording and action claims.
- Connector gate performs the actual CMMS write only after deterministic readiness is true.

### Data and Connectors

- Add roster/on-call schedule abstraction.
- Add trade and skill eligibility mapping.
- Add CMMS create-work-order connector action.
- Add optional CMMS assign-work-order connector action if the target CMMS separates create and assign.
- Add idempotency keys per workflow action.

### API Shape

- Add an action plan object with ordered steps:
  - `create_work_order`
  - `assign_work_order`
- Add action states:
  - `planned`
  - `blocked`
  - `needs_review`
  - `ready`
  - `sent`
  - `succeeded`
  - `failed`
- Add workflow action audit records or extend workflow trace with action step metadata.
- Add admin review endpoint for blocked or partial action plans.

### Safety Gates

- Work order creation requires valid request, valid environment, passing output contract, passing safety review, handoff readiness, connector enabled, and scoped key permission.
- Assignment requires resolved technician, eligible trade/skill, active shift, and environment policy allowing assignment.
- If creation succeeds and assignment fails, the workflow must not create a duplicate work order on retry.
- Final response may claim creation or assignment only from connector-confirmed facts.

### Tests

- Ready handoff sends one create request with idempotency key.
- Disabled connector blocks creation.
- Missing metadata review blocks creation when required.
- Roster exact match assigns the on-duty technician.
- Roster ambiguity requires review.
- Assignment failure preserves created work order id and does not duplicate on retry.
- API key scopes prevent non-admin/generated AI keys from admin action routes.

### Skill Usage

- `superpowers:using-git-worktrees` before implementation if the working tree remains dirty.
- `superpowers:writing-plans` for a task-by-task implementation plan.
- `superpowers:test-driven-development` for connector gates, idempotency, roster selection, and permission scopes.
- `superpowers:systematic-debugging` for connector failures and partial workflow states.
- `superpowers:requesting-code-review` before merging because this changes production-facing write behavior.
- `superpowers:verification-before-completion` before completion.
- `superpowers:finishing-a-development-branch` once tests pass and the branch is ready.

## Project 3: Inventory Check and Conditional Purchase Request Workflow

### Outcome

The system can check whether required parts are available and create or prepare a purchase request when policy allows it.

After this project, the full target request can execute as a controlled workflow:

- Resolve `AHU-3`.
- Create a high-priority work order.
- Assign it to tonight's on-duty technician.
- Resolve required filter SKU and quantity.
- Check inventory availability.
- If stock is insufficient, create or draft a purchase request according to policy.
- Explain the reason using recorded facts.

### Agents and Deterministic Components

- Parts Agent resolves required filter SKU and quantity from configured BOM or asset-type mapping.
- Inventory Agent summarizes stock lookup results.
- Procurement Agent drafts purchase request details.
- Policy layer decides whether purchase request creation is automatic or human-approved.
- Safety Reviewer Agent verifies final claims against action results.

### Data and Connectors

- Add inventory connector abstraction.
- Add purchase request connector abstraction.
- Add part catalog, unit, quantity, supplier, cost center, and reorder policy fields.
- Add optional stock reservation support only if the target inventory system supports safe reservation.
- Add procurement approval policy per environment.

### API Shape

- Extend action plan with:
  - `resolve_parts`
  - `check_inventory`
  - `create_purchase_request`
- Add evidence records for each explanation claim:
  - asset id
  - part SKU
  - required quantity
  - available quantity
  - stock location
  - reorder threshold
  - purchase request id or draft id
- Add admin UI views for inventory and procurement action status.

### Safety Gates

- Purchase request creation defaults to human review unless explicitly enabled.
- A purchase request requires resolved asset, resolved part SKU, quantity, cost center, supplier or procurement route, and scoped permission.
- Inventory lookup failures must not be treated as zero stock.
- If stock is available, the workflow must not create a purchase request.
- Final explanation must cite workflow facts, not free-form model guesses.

### Tests

- Available stock skips purchase request.
- Zero stock creates purchase request draft by default.
- Auto-create purchase request is blocked unless policy and scope allow it.
- Inventory timeout leads to `needs_review`, not purchase.
- Unknown SKU blocks procurement.
- Explanation cites structured evidence.
- Retrying after procurement success does not duplicate purchase requests.

### Skill Usage

- `superpowers:brainstorming` for procurement policy and approval thresholds.
- `superpowers:writing-plans` for implementation plan.
- `superpowers:test-driven-development` for inventory and procurement workflow rules.
- `superpowers:systematic-debugging` for connector timeouts, bad payloads, and retry behavior.
- `superpowers:requesting-code-review` because procurement writes are high-risk.
- `superpowers:verification-before-completion` before completion.

## Recommended Architecture Pattern

Use a deterministic action plan as the bridge between language understanding and external writes.

The LLM may propose or summarize, but the server owns:

- Allowed action types.
- Required inputs per action.
- Readiness checks.
- Permission checks.
- Connector dispatch.
- Idempotency.
- Retry behavior.
- Final action status.
- Evidence used in explanations.

Suggested action plan shape:

```json
{
  "schema": "cmms_action_plan_v1",
  "run_id": 123,
  "environment_code": "DEFAULT",
  "actions": [
    {
      "action_id": "create_work_order",
      "type": "cmms.work_order.create",
      "status": "ready",
      "requires_review": false,
      "idempotency_key": "cmms-run-123-create-work-order"
    },
    {
      "action_id": "assign_work_order",
      "type": "cmms.work_order.assign",
      "status": "needs_review",
      "requires_review": true,
      "reasons": ["No on-duty technician roster connector is configured."]
    }
  ]
}
```

## Execution Order

1. Project 1 first, because asset context and parts hints improve intake quality without increasing write risk.
2. Project 2 second, because controlled create and assignment establish action orchestration, idempotency, and audit semantics.
3. Project 3 third, because inventory and procurement add another system boundary and higher financial risk.

## Definition of Done for the Full Goal

The system can handle the sample request end-to-end only when:

- `AHU-3` resolves to exactly one configured asset.
- The work order request validates as high priority under environment rules.
- CMMS connector create action is enabled and scoped.
- Tonight's technician resolves from configured roster data and passes eligibility rules.
- Filter SKU and quantity resolve from configured asset/BOM data.
- Inventory connector returns a reliable stock result.
- Procurement policy either allows auto-create or produces a reviewable purchase request draft.
- Every external write has an idempotency key, audit record, connector response, and workflow trace entry.
- Final user-facing wording is generated from recorded facts and passes safety review.

## Explicit Non-Goals

- No generic `/chat` endpoint.
- No direct Ollama exposure.
- No LLM-only write decisions.
- No automatic email sending.
- No silent purchase request creation without environment policy, scope, and audit.
- No assumption that an inventory lookup failure means out of stock.

## Open Decisions

- Which CMMS is the first real connector target for asset lookup, create, and assignment.
- Whether roster data lives in CMMS, a separate schedule system, or local environment tables.
- Whether inventory and procurement live in the same system or separate connectors.
- Whether purchase requests should ever auto-create, or always remain human-approved drafts.
- Which API key scope model should apply to each action type.

## Next Step

Create a separate implementation plan for Project 1 using `superpowers:writing-plans`, with TDD tasks for asset registry, asset resolution, asset context in intake responses, and regression tests.
