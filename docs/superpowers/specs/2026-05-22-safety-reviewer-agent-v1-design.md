# Safety Reviewer Agent v1 Design

## Goal

Add the first bounded multi-agent step to the CMMS Local AI API workflow: a
Safety Reviewer Agent that reviews contract-valid intake results for advisory
risks without changing deterministic validation gates or CMMS data.

## Scope

This design only changes the existing controlled `cmms-intake` workflow. It does
not add a new public endpoint, router agent, autonomous planner, LLM judge, CMMS
write-back, work order creation, email sending, backend audio route, or generic
chat endpoint.

The Reviewer Agent is a traceable workflow step. It is not allowed to modify:

- extracted fields
- normalized codes
- output contract validation
- environment validation
- `needs_human_review`
- draft text
- final deterministic response composition rules

## Chosen Approach

Add a dedicated Safety Reviewer Agent step inside the current deterministic
workflow.

The step uses the same local model family and prompt management system as the
rest of the portal, but it has its own prompt endpoint:

```text
cmms-intake-reviewer
```

This keeps reviewer behavior versioned, testable, and traceable without mixing
it into the existing `cmms-intake` extraction prompt.

## Workflow

The updated workflow is:

```text
Request
-> Model Extraction
-> Output Contract Validation
-> Environment Validation
-> Draft Generation
-> Safety Reviewer Agent
-> Deterministic Response Composition
```

The Reviewer Agent runs only after output contract validation passes.

If output contract validation fails:

- the reviewer step is skipped;
- the workflow trace records `safety_reviewer_agent` as `skipped`;
- the API response includes a disabled/skipped `review` block;
- environment validation remains skipped or not-run according to existing rules.

If output contract validation passes:

- the reviewer receives a compact context containing the normalized result,
  contract validation, environment validation, draft text, and advisory safety
  boundary;
- the reviewer returns fixed JSON;
- Python validates and normalizes the reviewer output;
- the final response includes a `review` block.

## Reviewer Output Contract

The model must return JSON only:

```json
{
  "status": "pass",
  "human_review_recommended": false,
  "risk_flags": [],
  "notes": []
}
```

Allowed values:

- `status`: `pass`, `warning`, or `fail`
- `human_review_recommended`: boolean
- `risk_flags`: array of strings
- `notes`: array of strings

Server-side normalization rules:

- invalid JSON returns a safe reviewer failure block;
- unknown `status` becomes `warning`;
- non-boolean `human_review_recommended` becomes `false`;
- non-array `risk_flags` or `notes` becomes an empty list;
- duplicate strings are removed;
- strings are stripped;
- long arrays are capped to protect response size;
- long strings are truncated to protect response size.

The reviewer output never overrides deterministic validation.

## API Response

`POST /api/ai/cmms-intake` gains a `review` block.

When reviewer runs:

```json
{
  "review": {
    "enabled": true,
    "status": "pass",
    "human_review_recommended": false,
    "risk_flags": [],
    "notes": [],
    "source": "safety_reviewer_agent"
  }
}
```

When reviewer is skipped:

```json
{
  "review": {
    "enabled": false,
    "status": "skipped",
    "human_review_recommended": false,
    "risk_flags": [],
    "notes": [],
    "source": "safety_reviewer_agent",
    "message": "Skipped because output contract validation failed."
  }
}
```

Existing response fields remain present and authoritative:

- `contract`
- `result`
- `ai_validation`
- `validation`
- `fields`
- `drafts`
- `trace`

## Prompt Versioning

Add `cmms-intake-reviewer` to supported prompt endpoints.

Seed a default active reviewer prompt with these rules:

- include `/no_think`;
- return JSON only;
- review for advisory safety risk;
- do not edit fields or codes;
- do not claim a work order was created;
- do not approve, dispatch, or send email;
- flag missing information, contradictions, unsafe promises, or over-confident
  draft language;
- keep output concise.

The reviewer prompt should be managed by the existing Prompt Version Manager,
Prompt A/B Comparison, Promotion Gate, and Test Suites systems.

## Workflow Trace

Add a new trace step:

```text
safety_reviewer_agent
```

Step behavior:

- `skipped` if output contract validation failed;
- `passed` if reviewer status is `pass`;
- `warning` if reviewer status is `warning`;
- `failed` if reviewer status is `fail` or reviewer output could not be parsed;
- records model, prompt id, prompt version, and duration;
- stores only safe summaries and counts in `output_json`.

Do not store secrets, API keys, cookies, raw audio, or authentication headers in
trace records.

## UI

The Test Console gets a small Safety Reviewer panel near the existing validation
sections.

Panel fields:

- status;
- human review recommended;
- risk flags;
- notes;
- skipped message when applicable.

No new top-level menu, agent playground, or autonomous workflow UI is included
in v1.

## Testing

Required checks:

1. Contract passed means reviewer runs.
2. Contract failed means reviewer is skipped.
3. Reviewer invalid JSON returns a safe reviewer failure block.
4. Reviewer warning appears in `review` without changing deterministic
   validation.
5. Reviewer output does not change `needs_human_review`.
6. Workflow trace includes `safety_reviewer_agent`.
7. `cmms-intake-reviewer` default active prompt is seeded.
8. Existing `cmms-intake` response remains backward compatible.
9. Existing saved test cases and suites continue to run.
10. No generic `/chat` route is added.
11. No CMMS write-back or email sending is added.

## Security And Safety

The Reviewer Agent is advisory only. It may recommend human review in its own
block, but deterministic Python validation remains the authority for gates.

The reviewer cannot create work orders, approve work, send email, modify CMMS
data, change configured code lists, or bypass authentication.

## Future Work

After Reviewer Agent v1 is stable, future slices may add:

- reviewer-specific saved test assertions;
- prompt comparison dashboards for reviewer prompt versions;
- deterministic code normalization improvements;
- optional LLM code normalization suggestion step;
- router/classifier workflow only after multiple stable workflows exist.
