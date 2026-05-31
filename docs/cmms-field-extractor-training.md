# CMMS Field Extractor Training Runbook

This runbook describes the local-only path for preparing, evaluating, training, importing, and rolling back `college-cmms-field-extractor-phi4-v1`.

## Safety Rules

- Do not commit raw CMMS records.
- Do not commit model artifacts.
- Do not train approval, CMMS write-back, email sending, authentication, or authorization behavior into the model.
- Keep deterministic validation, safety reviewer, handoff readiness, and CMMS connector gates authoritative.

## Local Checks

Run focused tests before and after training utility changes:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data tests.test_cmms_field_extractor_eval tests.test_extractor_model_config -v
```

Run intake regression checks before promotion:

```powershell
python -m unittest tests.test_fast_mode_intake_api tests.test_code_normalizer_intake_api tests.test_safety_reviewer tests.test_cmms_auto_push -v
```

## Dataset Flow

Prepare anonymized JSONL files under `data/cmms_field_extractor/`.

Expected split names:

```text
data/cmms_field_extractor/train.jsonl
data/cmms_field_extractor/eval.jsonl
data/cmms_field_extractor/locked_test.jsonl
```

The locked test file must not be used for training retries, prompt tuning, or threshold selection.

The assistant training target is semantic only: `request_type`, `asset_hint`, `priority`, `summary`, `missing_fields`, and `human_review_recommended`. Building and room are input code fields merged by the API and validated deterministically. Summary targets must be concise and no longer than 160 characters.

Training targets should use exact CMMS code casing, such as `HVAC`, `General Maintenance`, and `P3`. The API still performs deterministic casing normalization, but candidate models should be trained to emit validator-ready values.

When reviewing model failures, trace examples back to the source workbook before relabeling. Some descriptions are ambiguous without the source `Job Type`, such as generic "unit" repairs, event setup requests that mention HVAC/lights schedules, or location phrases like "mechanical room". Use the audit utility for source context:

```powershell
python training/cmms_field_extractor/audit_source_failures.py `
  --workbook "data/training data.XLSX" `
  --locked-test data/cmms_field_extractor/locked_test.jsonl `
  --predictions data/cmms_field_extractor/prepared/semantic_phi4_v4_max256_postprocessed_locked_test_25_predictions.jsonl
```

Do not move locked-test hard cases into training. Use them to define review rules, improve future source metadata, or create new non-locked examples from separate source rows.

## Training

Use a dedicated ML environment, then run:

```powershell
python training/cmms_field_extractor/train_unsloth.py `
  --data-path data/cmms_field_extractor/train.jsonl `
  --eval-path data/cmms_field_extractor/eval.jsonl `
  --output-dir models/cmms_field_extractor/lora-v1
```

## Evaluation

Evaluate baseline `qwen3:8b` and the candidate model against the same examples. Promotion requires the gates from the design spec:

- JSON parse success at least 98 percent.
- Contract validity at least 95 percent.
- Required field accuracy at least 90 percent.
- Priority accuracy at least 85 percent.
- Overlong structured `summary` output equal 0.
- Unexpected structured `building` or `room` output equal 0.
- Unsafe work-order-created claims equal 0.
- Validator bypass attempts equal 0.

## Ollama Import

After exporting the model or adapter to GGUF, create the local model:

```powershell
ollama create college-cmms-field-extractor-phi4-v1 -f training/cmms_field_extractor/Modelfile
```

Set the extractor route to the candidate:

```dotenv
EXTRACTOR_MODEL_NAME=college-cmms-field-extractor-phi4-v1
```

Leave `OLLAMA_MODEL` unchanged unless every model call should move to a new default.

## Rollback

To rollback, unset `EXTRACTOR_MODEL_NAME` or set it back to `qwen3:8b`, then restart the API process. The previous model remains available because extractor selection is configuration-only.
