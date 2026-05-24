# Fast Workflow Defaults And Canonical Cache

## Purpose

Make local CMMS orchestration testing fast enough for repeated operator use while preserving the controlled full-review path.

This pass changes the default `cmms-intake` behavior from the slower full multi-call workflow to a fast one-call extraction workflow. Full mode remains available per request and per environment.

## Workflow Modes

`ExtractFieldsRequest` now accepts optional `workflow_mode`:

- `fast`: one `extract-work-order-fields` model call, deterministic drafts, deterministic fast reviewer block, and deterministic orchestration planning.
- `full`: classifier, field extractor, code-normalizer, draft-generator, and safety-reviewer model calls.

If `workflow_mode` is omitted, the API reads `environments.default_workflow_mode`. New and demo environments default to `fast`.

## Environment Default

The `environments` table includes:

- `default_workflow_mode TEXT NOT NULL DEFAULT 'fast'`

Startup migration adds the column for existing databases. Environment create and patch requests accept `default_workflow_mode` with values `fast` or `full`.

The Environments UI exposes a `Default workflow` switch. Orchestration and Test Console workflow selectors sync from the selected environment while still allowing a per-request override.

## Fast Extraction Cache

Fast mode includes an in-memory canonical cache for extraction output only.

Cache properties:

- TTL: 10 minutes
- Max entries: 128
- Scope: fast-mode extraction JSON only
- Key material: environment code, prompt id, prompt version, model, temperature, building/priority code lists, and canonicalized text hash
- Response visibility: `fast_cache.status` reports `hit` or `miss`

Canonicalization normalizes safe local-test variants:

- casing and punctuation;
- `WO` and `work order`;
- `AHU 3` and `AHU-3`;
- `MECH 1` and `MECH-1`;
- token order for otherwise equivalent short requests.

It does not use embeddings or broad semantic similarity. Changes to key entities, such as `AHU-3` versus `AHU-4`, produce a cache miss.

## Safety Boundary

Fast mode cannot bypass live CMMS write-back controls. The connector gate adds `full_review_required_for_live_push` when fast mode is used with a non-dry-run connector. Dry-run orchestration is still allowed so operators can inspect the plan.

## Observed Local Smoke

On the local `qwen3:8b` setup used during implementation:

- canonical miss: about 14.6 seconds;
- similar canonical hit: about 0.27 seconds;
- changed asset miss: about 13.6 seconds.

These numbers are local runtime observations, not service-level guarantees.

## Validation

Automated tests cover:

- default API mode resolves to fast when omitted;
- explicit full mode still drives the existing full-pipeline tests;
- environment default workflow mode can be saved and listed;
- Orchestration and Test Console sync workflow selectors from the environment;
- canonical cache hits for similar request text;
- canonical cache misses when key entities change.

Verification command:

```bash
.\.venv\Scripts\python.exe -m pytest -q
```

Latest local result during this pass:

```text
187 passed, 13 warnings, 22 subtests passed
```
