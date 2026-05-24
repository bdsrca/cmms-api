# Architecture

The project is a secure API control plane around a private LLM route.

It has one job: turn messy maintenance input into a validated CMMS draft without giving the model direct power over the CMMS.

## Core layers

| Layer | Responsibility |
| --- | --- |
| Client surface | Test console, API clients, future mobile intake, voice, screenshot upload. |
| Token gateway | Validates free tokens, paid tokens, scopes, expiry, quota, and environment access. |
| Intake normalizer | Cleans text, transcript, or image-derived content into an intake request. |
| Private LLM gateway | Routes the request to a company-controlled model endpoint. |
| Fast workflow selector | Chooses `fast` or `full` from the request override or the selected environment default. |
| Fast extraction cache | Reuses short-lived canonical fast-mode extraction results for similar test requests when key entities stay stable. |
| Output contract validator | Confirms the model returned the expected JSON shape. |
| Environment validator | Checks extracted values against CMMS code lists and rules. |
| Orchestration planner | Resolves configured assets, assignment roster, inventory, procurement draft lines, action plan, and operator summary. |
| Review package builder | Returns normalized fields, warnings, confidence, and next action. |
| Audit logger | Stores safe metadata, not private raw payloads by default. |

## Main boundary

The browser does not call the model directly. The CMMS database is not written directly by the model. The API sits in the middle and applies policy.

That middle layer is the important engineering work.

## Why this shape works

A CMMS environment is full of controlled values. If the model says `urgent`, the system still needs to know whether the target environment uses `URGENT`, `HIGH`, `P1`, `EMERGENCY`, or something else.

A strong architecture separates three concerns:

1. Language understanding.
2. CMMS field validation.
3. Operational action.

When those are separate, the project can grow safely from text intake to voice, screenshots, analytics, and multi-agent workflows.

## Fast and full workflows

`POST /api/ai/cmms-intake` supports two workflow modes:

- `fast`: one field-extraction model call, deterministic drafts, deterministic reviewer placeholder, and deterministic orchestration context.
- `full`: classifier, field extractor, code-normalization suggestion agent, draft generator, and safety reviewer agent.

If a request omits `workflow_mode`, the API uses the selected environment's `default_workflow_mode`. New and demo environments default to `fast` for local operator testing. Operators can switch an environment to `full` from the Environments page or override the mode per request.

Fast mode is not a live-write bypass. The controlled CMMS connector blocks live push when fast mode is used against a non-dry-run connector. Dry-run planning can still proceed so operators can inspect action plans, assignment targets, inventory status, and procurement drafts.

## Canonical fast cache

The fast extraction cache is an in-memory, short-TTL optimization for repeated local testing. It caches only the extracted field JSON from fast mode, not the entire work-order result.

The cache key includes:

- environment code;
- prompt id, prompt version, model, and temperature;
- active building and priority code lists;
- a canonicalized text hash.

Canonicalization normalizes safe variants such as casing, punctuation, `WO` versus `work order`, `AHU 3` versus `AHU-3`, and `MECH 1` versus `MECH-1`. It does not use embedding similarity. Entity changes such as asset, room, or priority changes produce a different canonical key and miss the cache.
