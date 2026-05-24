# Code Normalization Suggestion Agent v1 Design

## Goal

Add the next bounded multi-agent step to the CMMS Local AI API workflow: a Code
Normalization Suggestion Agent that proposes configured CMMS codes when extracted
values are ambiguous, multilingual, or not directly matched by deterministic
code-list validation.

The agent is advisory. It may suggest a code, confidence, and reason, but it
must not directly rewrite API output or bypass deterministic validation rules.

## Scope

This design changes only the controlled `cmms-intake` workflow. It does not add:

- a Router Agent;
- autonomous planning;
- a generic `/chat` endpoint;
- an LLM judge;
- backend audio upload;
- new CMMS write-back paths;
- email sending;
- direct Ollama exposure.

The first version focuses on code suggestion for these fields:

- `priority`
- `work_order_type`
- `job_type`
- `assign_to`
- `issue_to`

`building` and `room` stay deterministic in v1 because location matching is
usually more operationally sensitive and already has code/description/alias
matching.

## Required Pre-Fixes

Before adding the agent step, implementation must fix four existing pipeline
details that would otherwise hide or distort the values the normalizer needs.

### Preserve Raw Extraction

Current priority validation falls back to `NORMAL` when the extracted value is
not in the configured priority list. That fallback can stay for
backward-compatible validated fields, but the raw model output must also be
preserved.

The intake pipeline should carry:

```json
{
  "raw_extracted_fields": {
    "priority": "urgent phrase"
  },
  "validated_fields": {
    "priority": "NORMAL"
  },
  "invalid_code_candidates": {
    "priority": "urgent phrase"
  }
}
```

The normalizer must use raw extracted values plus redacted original request text,
not only fallback-adjusted fields.

### Fix Issue-To Category Mapping

The configured code category is:

```text
issue_to_employee_number
```

The default validation rule for `issue_to` must map to
`issue_to_employee_number`, not `issue_to`. This keeps deterministic validation
and the future normalizer aligned.

### Move Draft Generation Later

Draft generation currently happens inside the model extraction step before
contract validation and environment validation. Implementation must move draft
generation after code normalization and environment validation so drafts use the
final visible normalized values.

### Extend Public Response Model

`IntakeResponse` must include:

```python
code_normalization: dict[str, Any] | None = None
```

Otherwise FastAPI response-model filtering can remove the new response block.

## Chosen Approach

Use one optional LLM workflow step after output contract validation and before
environment validation:

```text
Request
-> Classifier Agent
-> Field Extractor Agent
-> Output Contract Validation
-> Code Normalization Suggestion Agent
-> Environment Validation
-> Draft Generation
-> Safety Reviewer Agent
-> CMMS Auto-Push Gate
-> Deterministic Response Composition
```

The suggestion agent receives:

- the contract-valid extracted result;
- the preserved raw extracted fields;
- invalid code candidates produced during initial extraction validation;
- the selected `environment_code`;
- enabled code-list values for supported categories;
- the original request text in a redacted/truncated form;
- a strict instruction to return suggestions only.

Python then applies deterministic acceptance rules. The agent never mutates the
payload by itself.

## Why This Agent Comes Next

The project already has deterministic validation, output contracts, workflow
trace, prompt versioning, saved test cases, test suites, prompt promotion gates,
and the Safety Reviewer Agent. That means a new agent step can be measured and
rolled back safely.

Code normalization is a good next agent because it solves a practical CMMS
problem:

- users may say `urgent`, `asap`, or a Chinese/French phrase meaning urgent;
- configured priorities may be `URGENT`, `NORMAL`, `LOW`;
- deterministic alias matching may not contain every language or phrase.

The agent can suggest `URGENT`, but deterministic validation still decides
whether the suggestion is accepted.

## Agent Output Contract

The model must return JSON only:

```json
{
  "suggestions": [
    {
      "field": "priority",
      "input_value": "urgent phrase",
      "suggested_code": "URGENT",
      "confidence": 0.86,
      "reason": "The user expressed urgency."
    }
  ]
}
```

Allowed fields:

- `priority`
- `work_order_type`
- `job_type`
- `assign_to`
- `issue_to`

Server-side normalization rules:

- invalid JSON returns a safe failed suggestion block;
- unknown fields are ignored;
- `suggested_code` must exist in the mapped enabled code list;
- confidence is clamped between `0` and `1`;
- reason strings are stripped and length-limited;
- duplicate field suggestions are reduced to the highest-confidence valid
  suggestion;
- unsupported or disabled code values are rejected.

## Deterministic Acceptance Rules

Python owns the decision to accept or reject a suggestion.

A suggestion can be accepted only when:

1. Output contract validation passed.
2. The field is supported by v1.
3. The current extracted field is missing, invalid, or not code-list matched.
4. The suggested code exists in the enabled code list for the environment.
5. Confidence is at or above the configured threshold.
6. The environment validation rule for the field allows normalization.

Default threshold:

```text
0.80
```

Accepted suggestions are visible in the response and trace. Do not silently fix
fields.

Rejected suggestions are also visible with a reason such as:

- `unsupported_field`
- `code_not_configured`
- `confidence_below_threshold`
- `field_already_valid`
- `contract_invalid`

## API Response Shape

`POST /api/ai/cmms-intake` gains a `code_normalization` block:

```json
{
  "code_normalization": {
    "enabled": true,
    "status": "applied",
    "suggestions": [
      {
        "field": "priority",
        "input_value": "urgent phrase",
        "suggested_code": "URGENT",
        "confidence": 0.86,
        "reason": "The user expressed urgency.",
        "decision": "accepted"
      }
    ],
    "applied": {
      "priority": "URGENT"
    },
    "rejected": []
  }
}
```

When skipped:

```json
{
  "code_normalization": {
    "enabled": false,
    "status": "skipped",
    "suggestions": [],
    "applied": {},
    "rejected": [],
    "message": "Skipped because output contract validation failed."
  }
}
```

Existing fields remain authoritative:

- `contract`
- `result`
- `ai_validation`
- `validation`
- `review`
- `cmms_push`
- `trace`

## Prompt Versioning

Add a new prompt endpoint:

```text
cmms-code-normalizer
```

Implementation must add this endpoint to the existing prompt endpoint registry
and seed a default active prompt:

```text
SUPPORTED_PROMPT_ENDPOINTS += {"cmms-code-normalizer"}
DEFAULT_PROMPT_VERSIONS["cmms-code-normalizer"] = ...
```

The default active prompt must:

- include `/no_think`;
- return JSON only;
- use configured CMMS codes only;
- never invent codes;
- never rewrite free-text summary;
- never claim a work order was created;
- provide concise reasons;
- handle English, Chinese, French, Spanish, Japanese, Korean, and mixed input.

The prompt is managed by the existing Prompt Version Manager, Prompt A/B
Comparison, Promotion Gate, and Test Suite infrastructure.

## Workflow Trace

Add a trace step:

```text
code_normalization_suggestion_agent
```

Step status:

- `skipped` when output contract validation fails or no environment code is
  available;
- `passed` when suggestions are valid and either accepted or cleanly rejected;
- `warning` when suggestions are rejected but no workflow failure occurs;
- `failed` when the model output cannot be parsed or normalized safely.

Trace output stores only safe summaries:

- suggestion count;
- accepted count;
- rejected count;
- rejected reasons;
- prompt id/version;
- model;
- duration.

Do not store API keys, session cookies, connector secrets, passwords, full
headers, raw audio, or full sensitive request text.

## UI

Test Console gets a compact Code Normalization panel near Contract Validation
and Environment Validation.

Show:

- status;
- accepted suggestions;
- rejected suggestions;
- before and after values;
- confidence;
- reason.

No new top-level menu is needed in v1.

Prompt Versions should list `cmms-code-normalizer` like other managed prompts.

## Testing

Required tests:

1. Raw extracted priority is preserved before fallback to `NORMAL`.
2. `invalid_code_candidates.priority` captures an unconfigured urgent phrase.
3. Default `issue_to` validation maps to `issue_to_employee_number`.
4. Contract failure skips the code normalizer.
5. Missing/invalid priority can accept a configured `URGENT` suggestion.
6. Suggested code not in the environment code list is rejected.
7. Low confidence suggestion is rejected.
8. Already-valid field is not overwritten.
9. Multilingual urgency input can produce a visible suggestion.
10. `ai_validation.normalized` shows what changed.
11. Workflow trace includes `code_normalization_suggestion_agent`.
12. Prompt endpoint `cmms-code-normalizer` is seeded.
13. `IntakeResponse` does not filter out `code_normalization`.
14. Draft generation runs after code normalization and environment validation.
15. Test Console shows the code normalization block.
16. Existing Safety Reviewer Agent still runs after normalization.
17. Existing CMMS auto-push gates still require contract, validation, review, and
    metadata readiness.
18. No generic `/chat`, LLM judge, Router Agent, backend audio upload, new
    write-back route, or email sending is added.

## Security And Safety

The Code Normalization Suggestion Agent is advisory and bounded. It cannot:

- create work orders;
- approve requests;
- send email;
- write to CMMS;
- change code lists;
- change validation rules;
- bypass output contracts;
- bypass environment validation;
- bypass Safety Reviewer or CMMS auto-push gates.

All accepted changes must be visible in `code_normalization` and deterministic
validation output.

## Future Work

Future slices may add:

- per-environment confidence thresholds;
- support for building/room suggestions after stronger location tests exist;
- saved test assertions for accepted/rejected suggestions;
- prompt comparison dashboard for `cmms-code-normalizer`;
- Router Agent only after multiple stable workflows exist.
