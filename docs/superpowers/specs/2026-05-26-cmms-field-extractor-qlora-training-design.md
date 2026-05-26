# CMMS Field Extractor QLoRA Training Design

Date: 2026-05-26

## Purpose

Train a local Qwen3 8B LoRA adapter that improves CMMS work-request field extraction while preserving the existing deterministic safety boundary.

The model remains advisory. It may extract and suggest structured fields, but it must not approve requests, write to CMMS, send email, expose Ollama directly, bypass validation, or claim that a work order was created.

## Scope

### In Scope

- Supervised fine-tuning for the field extractor task.
- Local QLoRA training against Qwen3 8B Instruct Hugging Face weights.
- Training data preparation from anonymized CMMS intake examples.
- Train, eval, and locked-test JSONL splits.
- Evaluation against JSON parsing, output contract, field accuracy, safety, and hallucination checks.
- Export path for LoRA adapter, merged model if needed, GGUF conversion, quantization, and Ollama import.
- API model routing update after the fine-tuned model passes evaluation.

### Out of Scope

- Full-model fine-tuning.
- Training a general CMMS agent.
- Training CMMS write-back, approval, authentication, authorization, billing, process control, or email behavior.
- Replacing deterministic contract validation, environment validation, safety reviewer gates, handoff readiness checks, or CMMS connector gates.
- Adding a generic chat endpoint or exposing Ollama directly.

## Recommended Approach

Use a single QLoRA supervised fine-tuning adapter for field extraction first.

This is preferred over prompt-only tuning because the extraction task has strict, measurable outputs and enough repeated structure to benefit from fine-tuning. It is preferred over multi-adapter training because the first production risk is extraction reliability, not broad agent behavior.

The first model identity should be:

```text
cmms-field-extractor-qwen3-8b-lora-v1
```

## Model Responsibility

The fine-tuned extractor receives a plain-language CMMS intake request and returns strict JSON only.

Target output:

```json
{
  "request_type": "work_order_request",
  "building": "North Campus",
  "room": "B204",
  "asset_hint": "AHU-3",
  "priority": "urgent",
  "summary": "Water dripping from ceiling near AHU-3 in room B204",
  "missing_fields": [],
  "human_review_recommended": false
}
```

Field notes:

- `request_type` must use the existing controlled request type vocabulary.
- `building`, `room`, and `asset_hint` may be `null` when missing or ambiguous.
- `priority` must use the configured priority vocabulary.
- `summary` must be concise and must not include unsupported operational claims.
- `missing_fields` lists fields needed for review or completion.
- `human_review_recommended` flags ambiguous, risky, incomplete, or policy-sensitive requests.

## Training Data

### Sources

Use only examples that are safe to store locally in the training corpus:

- Synthetic CMMS examples written for this project.
- Existing test cases converted into training/eval examples.
- Real work-order examples only after anonymization and review.
- Prompt comparison or operator correction data only when it has no secrets, private customer identifiers, API keys, tenant IDs, production URLs, raw CMMS IDs, or proprietary work-order records.

### Data Shape

Use chat-style JSONL so the training format matches the deployed instruction style.

Example:

```json
{"messages":[{"role":"system","content":"Extract CMMS work request fields. Return strict JSON only. Never claim a work order was created."},{"role":"user","content":"There is water dripping from the ceiling in room B204 at North Campus."},{"role":"assistant","content":"{\"request_type\":\"work_order_request\",\"building\":\"North Campus\",\"room\":\"B204\",\"asset_hint\":null,\"priority\":\"urgent\",\"summary\":\"Water dripping from ceiling in room B204\",\"missing_fields\":[],\"human_review_recommended\":false}"}]}
```

### Data Volume

V1 targets:

- Minimum useful: 300 to 500 examples.
- Good v1: 1,000 to 2,000 examples.
- Strong v1: 5,000 or more examples.

Quality is more important than volume. The dataset must include common maintenance phrasing, missing-field cases, ambiguous site names, asset aliases, safety-sensitive issues, low-priority requests, urgent failures, non-maintenance requests, and malformed input.

### Split Policy

Use deterministic splits:

- Train: 70 percent.
- Eval: 15 percent.
- Locked test: 15 percent.

The locked test set must not be used for prompt tuning, threshold selection, training retries, or example selection. It is only used to accept or reject a release candidate.

## Anonymization and Normalization

Before training, examples must pass a local preparation step that:

- Replaces names, emails, phone numbers, tenant identifiers, addresses, URLs, vendor names, API keys, work-order IDs, and customer-specific codes.
- Preserves useful operational structure such as building aliases, room formats, asset hints, and priority language.
- Normalizes priority labels to the configured environment vocabulary.
- Normalizes expected JSON keys and null handling.
- Rejects examples that contain secrets or cannot be safely anonymized.

The prepared dataset should be reproducible from source examples, but raw sensitive examples must not be committed to the repository.

## Training Method

Use QLoRA SFT rather than full fine-tuning.

Recommended first implementation:

- Base model: Qwen3 8B Instruct Hugging Face weights.
- Method: QLoRA supervised fine-tuning.
- Precision: 4-bit base loading during training.
- Output: LoRA adapter.
- Initial tooling preference: Unsloth for the first local v1 because it is lightweight and has a straightforward adapter-to-GGUF path.
- Alternative tooling: Axolotl for a more declarative repeatable training pipeline, or PEFT/TRL for lower-level control.

The repository should treat the training output as an artifact, not source code. Large model files, adapters, merged weights, and GGUF files should remain outside git unless a separate artifact policy is added.

## Evaluation Gates

A model candidate can be promoted only if it passes both model-level and system-level checks.

Model-level checks:

- JSON parse success is at least 98 percent.
- Output contract validity is at least 95 percent.
- Required field accuracy is at least 90 percent.
- Priority accuracy is at least 85 percent.
- Hallucinated building or room rate is at most 2 percent.
- Unsafe work-order-created claim count is 0.
- Validator bypass attempt count is 0.

System-level checks:

- Existing CMMS intake tests still pass.
- Output contract validation still runs before environment validation.
- Environment validation remains authoritative for building, room, priority, and review requirements.
- Safety reviewer and handoff readiness gates still block CMMS push when required.
- The API still does not expose Ollama directly.
- No generic chat endpoint is added.

## Deployment Flow

The intended release flow is:

```text
raw CMMS examples
-> anonymize / normalize
-> split train/eval/test
-> SFT QLoRA training
-> eval against contract and safety tests
-> export adapter
-> optionally merge adapter into base model
-> convert to GGUF
-> quantize to Q4_K_M or Q5_K_M
-> create Ollama model
-> route extractor calls to the new local model
-> run intake regression tests
```

Ollama model naming should include task, base model, and version:

```text
cmms-field-extractor-qwen3-8b-lora-v1
```

The API should select the model through configuration, not hard-coded route changes.

## Error Handling

Training data preparation should fail closed when it detects secrets or unsupported examples.

Evaluation should report failures by category:

- Invalid JSON.
- Contract mismatch.
- Missing required field.
- Wrong priority.
- Hallucinated location.
- Unsupported action claim.
- Unexpected extra fields.
- Human review flag mismatch.

Deployment should keep the previous model available so the operator can roll back by configuration.

## Testing Strategy

The implementation plan should add focused tests for:

- Dataset schema validation.
- Anonymization rejection of secrets.
- Deterministic split reproducibility.
- Evaluation metric calculation.
- Locked test protection.
- Model config selection for extractor routing.
- Regression checks proving CMMS push gates still block unsafe writes.

Manual smoke checks should compare baseline `qwen3:8b` and `cmms-field-extractor-qwen3-8b-lora-v1` on the same intake examples before promotion.

## Acceptance Criteria

The design is complete when:

- A reproducible local training/evaluation pipeline exists.
- The v1 extractor adapter is trained from anonymized examples only.
- The locked test set passes the defined gates.
- The fine-tuned model can be loaded through Ollama under the v1 model name.
- Existing intake, validation, safety reviewer, handoff, and CMMS connector gate behavior remains authoritative.
- Rollback to the previous model is possible through configuration.

## Risks

- Poor anonymization could leak sensitive operational data into model artifacts.
- Overfitting to synthetic examples could reduce performance on real operator language.
- A model with better fluency could sound more confident while still producing wrong fields.
- GGUF conversion or adapter import may differ by model architecture and tool version.
- Treating fine-tuning as a replacement for deterministic validation would weaken the system.

## Open Decisions for Implementation Planning

- Choose Unsloth, Axolotl, or PEFT/TRL for the first training script.
- Define exact dataset directory names and artifact paths.
- Decide whether v1 deploys as a GGUF adapter attached to a base model or as a merged quantized GGUF.
- Decide whether eval examples should be generated from existing tests first or from a new curated dataset first.
- Decide which environment configuration key selects the extractor model name.
