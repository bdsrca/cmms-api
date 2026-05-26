# CMMS Field Extractor QLoRA Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible local data preparation, evaluation, training, and Ollama deployment path for a Qwen3 8B CMMS field extractor LoRA adapter without weakening the existing CMMS safety gates.

**Architecture:** Keep training utilities separate from runtime API code. Add small focused modules under `training/cmms_field_extractor/` for schema validation, anonymization, deterministic splits, and evaluation. Runtime changes are limited to extractor model configuration so the fine-tuned model can be selected for field extraction while reviewer, draft, validation, handoff, and connector gates remain unchanged.

**Tech Stack:** Python 3.10+, unittest, FastAPI existing app modules, JSONL chat data, optional Unsloth/TRL/PEFT training script, llama.cpp/Ollama GGUF deployment.

---

## File Structure

- Create: `training/cmms_field_extractor/__init__.py`
  - Package marker for local training helpers.
- Create: `training/cmms_field_extractor/schema.py`
  - Validates chat JSONL records and assistant extractor payloads.
- Create: `training/cmms_field_extractor/anonymize.py`
  - Rejects secrets and normalizes examples into safe JSONL-ready records.
- Create: `training/cmms_field_extractor/split.py`
  - Deterministically splits records into train, eval, and locked test files.
- Create: `training/cmms_field_extractor/evaluate.py`
  - Computes model-output metrics against expected extractor payloads.
- Create: `training/cmms_field_extractor/train_unsloth.py`
  - Optional local training entrypoint that stays outside normal test execution.
- Create: `training/cmms_field_extractor/Modelfile.example`
  - Example Ollama Modelfile for importing the fine-tuned model or adapter.
- Create: `data/cmms_field_extractor/.gitkeep`
  - Keeps the data directory structure without committing datasets.
- Create: `data/cmms_field_extractor/README.md`
  - Documents local-only dataset and artifact policy.
- Modify: `.gitignore`
  - Ignore local training datasets and model artifacts while preserving `.gitkeep` and README.
- Modify: `app/config.py`
  - Add extractor-specific model configuration constants.
- Modify: `app/ai_endpoints.py`
  - Use the extractor model only for the field extraction call path.
- Create: `tests/test_cmms_field_extractor_training_data.py`
  - Unit tests for schema validation, anonymization, and split behavior.
- Create: `tests/test_cmms_field_extractor_eval.py`
  - Unit tests for evaluation metrics and failure categories.
- Create: `tests/test_extractor_model_config.py`
  - Unit tests proving extractor calls can use a dedicated model while other calls keep the default model.
- Modify: `.env.example`
  - Document optional extractor model override.
- Create: `docs/cmms-field-extractor-training.md`
  - Operator/developer runbook for data prep, eval, training, export, Ollama import, and rollback.

---

### Task 1: Dataset Directory and Artifact Policy

**Files:**
- Modify: `.gitignore`
- Create: `data/cmms_field_extractor/.gitkeep`
- Create: `data/cmms_field_extractor/README.md`

- [ ] **Step 1: Write the failing artifact policy test**

Create `tests/test_cmms_field_extractor_training_data.py` with this initial content:

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CmmsFieldExtractorTrainingDataPolicyTests(unittest.TestCase):
    def test_training_data_directory_documents_local_only_policy(self) -> None:
        readme = ROOT / "data" / "cmms_field_extractor" / "README.md"

        self.assertTrue(readme.exists())
        text = readme.read_text(encoding="utf-8")
        self.assertIn("Do not commit raw CMMS records", text)
        self.assertIn("Do not commit model artifacts", text)
        self.assertIn("anonymized", text.lower())

    def test_gitignore_excludes_training_datasets_and_model_artifacts(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("data/cmms_field_extractor/*.jsonl", gitignore)
        self.assertIn("models/cmms_field_extractor/", gitignore)
        self.assertIn("*.gguf", gitignore)
        self.assertIn("!data/cmms_field_extractor/.gitkeep", gitignore)
        self.assertIn("!data/cmms_field_extractor/README.md", gitignore)
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorTrainingDataPolicyTests -v
```

Expected: FAIL because the data README and gitignore entries do not exist yet.

- [ ] **Step 3: Add the data directory marker**

Create an empty file:

```text
data/cmms_field_extractor/.gitkeep
```

- [ ] **Step 4: Add the data policy README**

Create `data/cmms_field_extractor/README.md`:

```markdown
# CMMS Field Extractor Local Data

This directory is for local CMMS field-extractor training data.

Do not commit raw CMMS records, customer data, tenant identifiers, API keys, production URLs, real work-order IDs, or model artifacts.

Only anonymized, reviewed, small sample fixtures may be committed when a test needs them. Normal training files such as `train.jsonl`, `eval.jsonl`, `locked_test.jsonl`, and generated model outputs must stay local.
```

- [ ] **Step 5: Update `.gitignore`**

Append this block to `.gitignore`:

```gitignore

# Local CMMS field extractor training data and artifacts
data/cmms_field_extractor/*.jsonl
data/cmms_field_extractor/raw/
data/cmms_field_extractor/prepared/
models/cmms_field_extractor/
*.gguf
*.safetensors
!data/cmms_field_extractor/.gitkeep
!data/cmms_field_extractor/README.md
```

- [ ] **Step 6: Run the policy test**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorTrainingDataPolicyTests -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add .gitignore data/cmms_field_extractor/.gitkeep data/cmms_field_extractor/README.md tests/test_cmms_field_extractor_training_data.py
git commit -m "Add CMMS extractor training data policy"
```

---

### Task 2: Training Record Schema Validation

**Files:**
- Create: `training/cmms_field_extractor/__init__.py`
- Create: `training/cmms_field_extractor/schema.py`
- Modify: `tests/test_cmms_field_extractor_training_data.py`

- [ ] **Step 1: Add failing schema tests**

Append this import near the top of `tests/test_cmms_field_extractor_training_data.py`:

```python
from training.cmms_field_extractor.schema import (
    REQUIRED_ASSISTANT_KEYS,
    assistant_payload_errors,
    validate_chat_record,
)
```

Append these tests:

```python
class CmmsFieldExtractorSchemaTests(unittest.TestCase):
    def valid_record(self) -> dict:
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "Extract CMMS work request fields. Return strict JSON only.",
                },
                {
                    "role": "user",
                    "content": "Water is dripping from the ceiling in room B204 at North Campus.",
                },
                {
                    "role": "assistant",
                    "content": (
                        '{"request_type":"work_order_request",'
                        '"building":"North Campus",'
                        '"room":"B204",'
                        '"asset_hint":null,'
                        '"priority":"urgent",'
                        '"summary":"Water dripping from ceiling in room B204",'
                        '"missing_fields":[],'
                        '"human_review_recommended":false}'
                    ),
                },
            ]
        }

    def test_required_assistant_keys_match_design(self) -> None:
        self.assertEqual(
            REQUIRED_ASSISTANT_KEYS,
            {
                "request_type",
                "building",
                "room",
                "asset_hint",
                "priority",
                "summary",
                "missing_fields",
                "human_review_recommended",
            },
        )

    def test_valid_chat_record_has_no_errors(self) -> None:
        self.assertEqual(validate_chat_record(self.valid_record()), [])

    def test_rejects_missing_required_assistant_key(self) -> None:
        record = self.valid_record()
        record["messages"][2]["content"] = (
            '{"request_type":"work_order_request",'
            '"building":"North Campus",'
            '"room":"B204",'
            '"asset_hint":null,'
            '"priority":"urgent",'
            '"summary":"Water dripping",'
            '"human_review_recommended":false}'
        )

        self.assertIn("assistant.missing_fields:missing", validate_chat_record(record))

    def test_rejects_extra_assistant_key(self) -> None:
        payload = {
            "request_type": "work_order_request",
            "building": "North Campus",
            "room": "B204",
            "asset_hint": None,
            "priority": "urgent",
            "summary": "Water dripping",
            "missing_fields": [],
            "human_review_recommended": False,
            "work_order_created": True,
        }

        self.assertIn("assistant.extra:work_order_created", assistant_payload_errors(payload))

    def test_rejects_unsafe_created_claim_in_summary(self) -> None:
        payload = {
            "request_type": "work_order_request",
            "building": "North Campus",
            "room": "B204",
            "asset_hint": None,
            "priority": "urgent",
            "summary": "Work order created for water leak.",
            "missing_fields": [],
            "human_review_recommended": False,
        }

        self.assertIn("assistant.unsafe_claim:summary", assistant_payload_errors(payload))
```

- [ ] **Step 2: Run the failing schema tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorSchemaTests -v
```

Expected: FAIL with `ModuleNotFoundError` for `training.cmms_field_extractor.schema`.

- [ ] **Step 3: Add the package marker**

Create `training/cmms_field_extractor/__init__.py`:

```python
"""Local training utilities for the CMMS field extractor model."""
```

- [ ] **Step 4: Implement schema validation**

Create `training/cmms_field_extractor/schema.py`:

```python
"""Schema checks for CMMS field extractor training records."""

from __future__ import annotations

import json
from typing import Any


REQUIRED_ASSISTANT_KEYS = {
    "request_type",
    "building",
    "room",
    "asset_hint",
    "priority",
    "summary",
    "missing_fields",
    "human_review_recommended",
}

STRING_OR_NULL_KEYS = {"building", "room", "asset_hint", "priority", "summary"}
UNSAFE_CLAIMS = (
    "work order created",
    "created work order",
    "submitted work order",
    "sent email",
    "emailed",
)


def assistant_payload_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = REQUIRED_ASSISTANT_KEYS - set(payload)
    for key in sorted(missing):
        errors.append(f"assistant.{key}:missing")

    extra = set(payload) - REQUIRED_ASSISTANT_KEYS
    for key in sorted(extra):
        errors.append(f"assistant.extra:{key}")

    for key in STRING_OR_NULL_KEYS:
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"assistant.{key}:expected_string_or_null")

    if not isinstance(payload.get("request_type"), str):
        errors.append("assistant.request_type:expected_string")

    if not isinstance(payload.get("missing_fields"), list):
        errors.append("assistant.missing_fields:expected_list")

    if not isinstance(payload.get("human_review_recommended"), bool):
        errors.append("assistant.human_review_recommended:expected_bool")

    for key in ("summary",):
        value = payload.get(key)
        if isinstance(value, str) and any(claim in value.lower() for claim in UNSAFE_CLAIMS):
            errors.append(f"assistant.unsafe_claim:{key}")

    return errors


def validate_chat_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        return ["messages:expected_system_user_assistant"]

    expected_roles = ["system", "user", "assistant"]
    for index, role in enumerate(expected_roles):
        message = messages[index]
        if not isinstance(message, dict):
            errors.append(f"messages.{index}:expected_object")
            continue
        if message.get("role") != role:
            errors.append(f"messages.{index}.role:expected_{role}")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            errors.append(f"messages.{index}.content:expected_non_empty_string")

    assistant_content = messages[2].get("content") if isinstance(messages[2], dict) else None
    if isinstance(assistant_content, str):
        try:
            payload = json.loads(assistant_content)
        except json.JSONDecodeError:
            errors.append("assistant.content:invalid_json")
        else:
            if not isinstance(payload, dict):
                errors.append("assistant.content:expected_json_object")
            else:
                errors.extend(assistant_payload_errors(payload))

    return errors
```

- [ ] **Step 5: Run schema and policy tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add training/cmms_field_extractor/__init__.py training/cmms_field_extractor/schema.py tests/test_cmms_field_extractor_training_data.py
git commit -m "Add CMMS extractor training schema checks"
```

---

### Task 3: Anonymization and Normalization

**Files:**
- Create: `training/cmms_field_extractor/anonymize.py`
- Modify: `tests/test_cmms_field_extractor_training_data.py`

- [ ] **Step 1: Add failing anonymization tests**

Append this import:

```python
from training.cmms_field_extractor.anonymize import (
    SecretDetectedError,
    build_chat_record,
    normalize_expected_payload,
    reject_if_sensitive,
)
```

Append these tests:

```python
class CmmsFieldExtractorAnonymizationTests(unittest.TestCase):
    def test_rejects_email_phone_api_key_and_url(self) -> None:
        samples = [
            "Contact jane@example.com about the leak.",
            "Call 416-555-1212 when done.",
            "Use api_key sk-live-abc123 for the CMMS.",
            "Post it to https://cmms.example.com/workorders.",
        ]

        for sample in samples:
            with self.subTest(sample=sample):
                with self.assertRaises(SecretDetectedError):
                    reject_if_sensitive(sample)

    def test_normalizes_expected_payload(self) -> None:
        normalized = normalize_expected_payload(
            {
                "request_type": "Work_Order_Request",
                "building": "",
                "room": " B204 ",
                "asset_hint": "",
                "priority": "URGENT",
                "summary": "  Water leak near ceiling.  ",
                "missing_fields": ["building", "building"],
                "human_review_recommended": "yes",
            }
        )

        self.assertEqual(
            normalized,
            {
                "request_type": "work_order_request",
                "building": None,
                "room": "B204",
                "asset_hint": None,
                "priority": "urgent",
                "summary": "Water leak near ceiling.",
                "missing_fields": ["building"],
                "human_review_recommended": True,
            },
        )

    def test_build_chat_record_returns_valid_record(self) -> None:
        record = build_chat_record(
            user_text="Water leak in room B204 at North Campus.",
            expected={
                "request_type": "work_order_request",
                "building": "North Campus",
                "room": "B204",
                "asset_hint": None,
                "priority": "urgent",
                "summary": "Water leak in room B204",
                "missing_fields": [],
                "human_review_recommended": False,
            },
        )

        self.assertEqual(validate_chat_record(record), [])
        self.assertEqual(record["messages"][0]["role"], "system")
        self.assertIn("Return strict JSON only", record["messages"][0]["content"])
```

- [ ] **Step 2: Run the failing anonymization tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorAnonymizationTests -v
```

Expected: FAIL with `ModuleNotFoundError` or missing symbols.

- [ ] **Step 3: Implement anonymization helpers**

Create `training/cmms_field_extractor/anonymize.py`:

```python
"""Anonymization and normalization helpers for CMMS extractor training data."""

from __future__ import annotations

import json
import re
from typing import Any

from .schema import validate_chat_record


SYSTEM_PROMPT = (
    "Extract CMMS work request fields. Return strict JSON only. "
    "Never claim a work order was created."
)


class SecretDetectedError(ValueError):
    """Raised when a training example contains data that must not be stored."""


SENSITIVE_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "url": re.compile(r"https?://\S+", re.IGNORECASE),
    "api_key": re.compile(r"\b(?:api[_-]?key|token|secret|sk-[a-z0-9_-]+)\b", re.IGNORECASE),
}


def reject_if_sensitive(text: str) -> None:
    for name, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(text):
            raise SecretDetectedError(f"sensitive_{name}_detected")


def _clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_missing_fields(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        field = str(item).strip()
        if field and field not in seen:
            seen.add(field)
            result.append(field)
    return result


def normalize_expected_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_type": str(payload.get("request_type", "")).strip().lower(),
        "building": _clean_optional_string(payload.get("building")),
        "room": _clean_optional_string(payload.get("room")),
        "asset_hint": _clean_optional_string(payload.get("asset_hint")),
        "priority": _clean_optional_string(payload.get("priority")).lower()
        if _clean_optional_string(payload.get("priority"))
        else None,
        "summary": _clean_optional_string(payload.get("summary")),
        "missing_fields": _clean_missing_fields(payload.get("missing_fields")),
        "human_review_recommended": bool(payload.get("human_review_recommended")),
    }


def build_chat_record(user_text: str, expected: dict[str, Any]) -> dict[str, Any]:
    reject_if_sensitive(user_text)
    normalized = normalize_expected_payload(expected)
    assistant_content = json.dumps(normalized, separators=(",", ":"))
    record = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text.strip()},
            {"role": "assistant", "content": assistant_content},
        ]
    }
    errors = validate_chat_record(record)
    if errors:
        raise ValueError(f"invalid_training_record:{errors}")
    return record
```

- [ ] **Step 4: Run training data tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add training/cmms_field_extractor/anonymize.py tests/test_cmms_field_extractor_training_data.py
git commit -m "Add CMMS extractor anonymization helpers"
```

---

### Task 4: Deterministic Train/Eval/Locked-Test Split

**Files:**
- Create: `training/cmms_field_extractor/split.py`
- Modify: `tests/test_cmms_field_extractor_training_data.py`

- [ ] **Step 1: Add failing split tests**

Append this import:

```python
from training.cmms_field_extractor.split import split_records
```

Append these tests:

```python
class CmmsFieldExtractorSplitTests(unittest.TestCase):
    def test_split_records_is_deterministic_and_uses_expected_ratios(self) -> None:
        records = [{"id": f"example-{index}"} for index in range(20)]

        first = split_records(records, seed=7)
        second = split_records(records, seed=7)

        self.assertEqual(first, second)
        self.assertEqual(len(first["train"]), 14)
        self.assertEqual(len(first["eval"]), 3)
        self.assertEqual(len(first["locked_test"]), 3)

    def test_split_records_rejects_too_few_records(self) -> None:
        with self.assertRaises(ValueError):
            split_records([{"id": "one"}, {"id": "two"}])
```

- [ ] **Step 2: Run the failing split tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorSplitTests -v
```

Expected: FAIL because `training.cmms_field_extractor.split` does not exist.

- [ ] **Step 3: Implement deterministic split**

Create `training/cmms_field_extractor/split.py`:

```python
"""Deterministic train/eval/locked-test splitting."""

from __future__ import annotations

import random
from typing import Any


def split_records(
    records: list[dict[str, Any]],
    *,
    seed: int = 42,
    train_ratio: float = 0.70,
    eval_ratio: float = 0.15,
) -> dict[str, list[dict[str, Any]]]:
    if len(records) < 10:
        raise ValueError("at_least_10_records_required")

    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)

    train_count = int(len(shuffled) * train_ratio)
    eval_count = int(len(shuffled) * eval_ratio)

    train = shuffled[:train_count]
    eval_records = shuffled[train_count : train_count + eval_count]
    locked_test = shuffled[train_count + eval_count :]

    return {
        "train": train,
        "eval": eval_records,
        "locked_test": locked_test,
    }
```

- [ ] **Step 4: Run training data tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add training/cmms_field_extractor/split.py tests/test_cmms_field_extractor_training_data.py
git commit -m "Add deterministic CMMS extractor dataset split"
```

---

### Task 5: Evaluation Metrics and Failure Categories

**Files:**
- Create: `training/cmms_field_extractor/evaluate.py`
- Create: `tests/test_cmms_field_extractor_eval.py`

- [ ] **Step 1: Write failing evaluator tests**

Create `tests/test_cmms_field_extractor_eval.py`:

```python
import unittest

from training.cmms_field_extractor.evaluate import evaluate_predictions


EXPECTED = {
    "request_type": "work_order_request",
    "building": "North Campus",
    "room": "B204",
    "asset_hint": None,
    "priority": "urgent",
    "summary": "Water leak in room B204",
    "missing_fields": [],
    "human_review_recommended": False,
}


class CmmsFieldExtractorEvalTests(unittest.TestCase):
    def test_evaluate_predictions_counts_successful_output(self) -> None:
        report = evaluate_predictions(
            [
                {
                    "id": "ok",
                    "expected": EXPECTED,
                    "prediction": (
                        '{"request_type":"work_order_request",'
                        '"building":"North Campus",'
                        '"room":"B204",'
                        '"asset_hint":null,'
                        '"priority":"urgent",'
                        '"summary":"Water leak in room B204",'
                        '"missing_fields":[],'
                        '"human_review_recommended":false}'
                    ),
                }
            ]
        )

        self.assertEqual(report["total"], 1)
        self.assertEqual(report["json_parse_success_rate"], 1.0)
        self.assertEqual(report["contract_valid_rate"], 1.0)
        self.assertEqual(report["required_field_accuracy"], 1.0)
        self.assertEqual(report["priority_accuracy"], 1.0)
        self.assertEqual(report["unsafe_claim_count"], 0)
        self.assertEqual(report["failures"], [])

    def test_evaluate_predictions_reports_invalid_json_wrong_priority_and_unsafe_claim(self) -> None:
        report = evaluate_predictions(
            [
                {"id": "bad-json", "expected": EXPECTED, "prediction": "not json"},
                {
                    "id": "wrong-priority",
                    "expected": EXPECTED,
                    "prediction": (
                        '{"request_type":"work_order_request",'
                        '"building":"North Campus",'
                        '"room":"B204",'
                        '"asset_hint":null,'
                        '"priority":"low",'
                        '"summary":"Work order created for water leak",'
                        '"missing_fields":[],'
                        '"human_review_recommended":false}'
                    ),
                },
            ]
        )

        self.assertEqual(report["total"], 2)
        self.assertEqual(report["json_parse_success_rate"], 0.5)
        self.assertEqual(report["priority_accuracy"], 0.0)
        self.assertEqual(report["unsafe_claim_count"], 1)
        self.assertIn(
            {"id": "bad-json", "category": "invalid_json"},
            report["failures"],
        )
        self.assertIn(
            {"id": "wrong-priority", "category": "wrong_priority"},
            report["failures"],
        )
        self.assertIn(
            {"id": "wrong-priority", "category": "unsafe_claim"},
            report["failures"],
        )
```

- [ ] **Step 2: Run the failing evaluator tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_eval -v
```

Expected: FAIL because `training.cmms_field_extractor.evaluate` does not exist.

- [ ] **Step 3: Implement evaluator**

Create `training/cmms_field_extractor/evaluate.py`:

```python
"""Evaluation metrics for CMMS field extractor model outputs."""

from __future__ import annotations

import json
from typing import Any

from .schema import REQUIRED_ASSISTANT_KEYS, assistant_payload_errors


LOCATION_KEYS = ("building", "room")
REQUIRED_FIELD_KEYS = ("request_type", "building", "room", "priority", "summary")


def _rate(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


def _failure(example_id: str, category: str) -> dict[str, str]:
    return {"id": example_id, "category": category}


def evaluate_predictions(examples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(examples)
    parsed_count = 0
    contract_valid_count = 0
    required_field_matches = 0
    required_field_total = 0
    priority_matches = 0
    priority_total = 0
    hallucinated_location_count = 0
    unsafe_claim_count = 0
    failures: list[dict[str, str]] = []

    for example in examples:
        example_id = str(example.get("id", "unknown"))
        expected = example["expected"]
        prediction_text = example["prediction"]

        try:
            prediction = json.loads(prediction_text)
        except json.JSONDecodeError:
            failures.append(_failure(example_id, "invalid_json"))
            continue

        if not isinstance(prediction, dict):
            failures.append(_failure(example_id, "invalid_json_object"))
            continue

        parsed_count += 1
        schema_errors = assistant_payload_errors(prediction)
        if not schema_errors:
            contract_valid_count += 1
        else:
            failures.append(_failure(example_id, "contract_mismatch"))

        for key in REQUIRED_FIELD_KEYS:
            required_field_total += 1
            if prediction.get(key) == expected.get(key):
                required_field_matches += 1

        if expected.get("priority") is not None:
            priority_total += 1
            if prediction.get("priority") == expected.get("priority"):
                priority_matches += 1
            else:
                failures.append(_failure(example_id, "wrong_priority"))

        for key in LOCATION_KEYS:
            if expected.get(key) is None and prediction.get(key):
                hallucinated_location_count += 1
                failures.append(_failure(example_id, f"hallucinated_{key}"))

        if any(error.startswith("assistant.unsafe_claim") for error in schema_errors):
            unsafe_claim_count += 1
            failures.append(_failure(example_id, "unsafe_claim"))

        for extra_key in set(prediction) - REQUIRED_ASSISTANT_KEYS:
            failures.append(_failure(example_id, f"unexpected_extra_field:{extra_key}"))

    return {
        "total": total,
        "json_parse_success_rate": _rate(parsed_count, total),
        "contract_valid_rate": _rate(contract_valid_count, total),
        "required_field_accuracy": _rate(required_field_matches, required_field_total),
        "priority_accuracy": _rate(priority_matches, priority_total),
        "hallucinated_location_count": hallucinated_location_count,
        "unsafe_claim_count": unsafe_claim_count,
        "failures": failures,
    }
```

- [ ] **Step 4: Run evaluator tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_eval -v
```

Expected: PASS.

- [ ] **Step 5: Run all new training tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data tests.test_cmms_field_extractor_eval -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add training/cmms_field_extractor/evaluate.py tests/test_cmms_field_extractor_eval.py
git commit -m "Add CMMS extractor evaluation metrics"
```

---

### Task 6: Extractor-Specific Model Configuration

**Files:**
- Modify: `app/config.py`
- Modify: `app/ai_endpoints.py`
- Create: `tests/test_extractor_model_config.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_extractor_model_config.py`:

```python
import importlib
import os
import unittest
from unittest.mock import patch


class ExtractorModelConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("OLLAMA_MODEL", None)
        os.environ.pop("EXTRACTOR_MODEL_NAME", None)

    def test_extractor_model_defaults_to_global_model(self) -> None:
        os.environ.pop("OLLAMA_MODEL", None)
        os.environ.pop("EXTRACTOR_MODEL_NAME", None)

        import app.config as config

        importlib.reload(config)
        self.assertEqual(config.MODEL_NAME, "qwen3:8b")
        self.assertEqual(config.EXTRACTOR_MODEL_NAME, "qwen3:8b")

    def test_extractor_model_can_be_overridden_without_changing_global_model(self) -> None:
        os.environ["OLLAMA_MODEL"] = "qwen3:8b"
        os.environ["EXTRACTOR_MODEL_NAME"] = "cmms-field-extractor-qwen3-8b-lora-v1"

        import app.config as config

        importlib.reload(config)
        self.assertEqual(config.MODEL_NAME, "qwen3:8b")
        self.assertEqual(
            config.EXTRACTOR_MODEL_NAME,
            "cmms-field-extractor-qwen3-8b-lora-v1",
        )

    def test_call_extractor_model_uses_extractor_model_name(self) -> None:
        import app.ai_endpoints as ai_endpoints

        with patch.object(ai_endpoints, "EXTRACTOR_MODEL_NAME", "cmms-field-extractor-qwen3-8b-lora-v1"):
            self.assertEqual(
                ai_endpoints.extractor_model_name(),
                "cmms-field-extractor-qwen3-8b-lora-v1",
            )
```

- [ ] **Step 2: Run the failing config tests**

Run:

```powershell
python -m unittest tests.test_extractor_model_config -v
```

Expected: FAIL because `EXTRACTOR_MODEL_NAME` and `extractor_model_name` are not defined.

- [ ] **Step 3: Add config constants**

In `app/config.py`, replace the current model constant:

```python
MODEL_NAME = "qwen3:8b"
```

with:

```python
import os


MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3:8b")
EXTRACTOR_MODEL_NAME = os.getenv("EXTRACTOR_MODEL_NAME", MODEL_NAME)
```

If `app/config.py` already imports `os`, reuse the existing import rather than adding a duplicate.

- [ ] **Step 4: Add extractor model helper and use it in extraction calls**

In `app/ai_endpoints.py`, update the config import from:

```python
from .config import ADVISORY_WARNING, ALLOWED_REQUEST_TYPES, MODEL_NAME, OLLAMA_CHAT_URL
```

to:

```python
from .config import (
    ADVISORY_WARNING,
    ALLOWED_REQUEST_TYPES,
    EXTRACTOR_MODEL_NAME,
    MODEL_NAME,
    OLLAMA_CHAT_URL,
)
```

Add this helper near `call_ollama`:

```python
def extractor_model_name() -> str:
    return EXTRACTOR_MODEL_NAME
```

Find the field extraction model call for `/api/ai/extract-work-order-fields` and any full-mode `cmms-intake` model extraction call using `model=MODEL_NAME`. Change only the field extraction calls to:

```python
model=extractor_model_name(),
```

Do not change draft generator, safety reviewer, health endpoint, management endpoint, or generic model metadata in this task.

- [ ] **Step 5: Document `.env.example`**

Append:

```dotenv

# Optional: route only CMMS field extraction to a fine-tuned local extractor.
# Leave unset to use OLLAMA_MODEL / qwen3:8b.
EXTRACTOR_MODEL_NAME=cmms-field-extractor-qwen3-8b-lora-v1
```

- [ ] **Step 6: Run config tests**

Run:

```powershell
python -m unittest tests.test_extractor_model_config -v
```

Expected: PASS.

- [ ] **Step 7: Run focused intake tests**

Run:

```powershell
python -m unittest tests.test_fast_mode_intake_api tests.test_code_normalizer_intake_api tests.test_safety_reviewer -v
```

Expected: PASS. If any fake `call_ollama` signature lacks `model`, update the test fake to accept `model="qwen3:8b"` without changing assertions unrelated to this task.

- [ ] **Step 8: Commit**

```powershell
git add app/config.py app/ai_endpoints.py .env.example tests/test_extractor_model_config.py
git commit -m "Add extractor-specific model configuration"
```

---

### Task 7: Training Script Skeleton

**Files:**
- Create: `training/cmms_field_extractor/train_unsloth.py`
- Modify: `tests/test_cmms_field_extractor_training_data.py`

- [ ] **Step 1: Add failing import-safe training script test**

Append this test:

```python
class CmmsFieldExtractorTrainingScriptTests(unittest.TestCase):
    def test_training_script_import_is_dependency_safe(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        self.assertTrue(callable(train_unsloth.main))
        self.assertIn("data_path", train_unsloth.parse_args(["--data-path", "train.jsonl"]).__dict__)
```

- [ ] **Step 2: Run the failing training script test**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorTrainingScriptTests -v
```

Expected: FAIL because `train_unsloth.py` does not exist.

- [ ] **Step 3: Add dependency-safe training script skeleton**

Create `training/cmms_field_extractor/train_unsloth.py`:

```python
"""Optional Unsloth training entrypoint for the CMMS field extractor adapter.

This module is import-safe for normal test runs. Heavy ML dependencies are
imported inside `main` only.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CMMS field extractor QLoRA adapter.")
    parser.add_argument("--data-path", required=True, help="Path to train JSONL.")
    parser.add_argument("--eval-path", help="Path to eval JSONL.")
    parser.add_argument("--base-model", default="Qwen/Qwen3-8B-Instruct")
    parser.add_argument("--output-dir", default="models/cmms_field_extractor/lora-v1")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--num-train-epochs", type=float, default=2.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    if not data_path.exists():
        raise SystemExit(f"data_path_not_found:{data_path}")

    try:
        from datasets import load_dataset
        from trl import SFTTrainer
        from unsloth import FastLanguageModel
        from transformers import TrainingArguments
    except ImportError as exc:
        raise SystemExit(
            "Missing optional training dependencies. Install Unsloth, datasets, trl, and transformers "
            "in a dedicated training environment."
        ) from exc

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    dataset_files = {"train": str(data_path)}
    if args.eval_path:
        dataset_files["validation"] = args.eval_path
    dataset = load_dataset("json", data_files=dataset_files)

    def formatting_prompts_func(batch):
        texts = []
        for messages in batch["messages"]:
            texts.append(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False))
        return {"text": texts}

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset.get("validation"),
        formatting_func=None,
        args=TrainingArguments(
            output_dir=args.output_dir,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            num_train_epochs=args.num_train_epochs,
            learning_rate=args.learning_rate,
            logging_steps=10,
            save_strategy="epoch",
            eval_strategy="epoch" if "validation" in dataset else "no",
            report_to=[],
        ),
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        dataset_num_proc=2,
        packing=False,
    )
    dataset = dataset.map(formatting_prompts_func, batched=True)
    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run script import test**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorTrainingScriptTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add training/cmms_field_extractor/train_unsloth.py tests/test_cmms_field_extractor_training_data.py
git commit -m "Add CMMS extractor Unsloth training skeleton"
```

---

### Task 8: Ollama Modelfile and Training Runbook

**Files:**
- Create: `training/cmms_field_extractor/Modelfile.example`
- Create: `docs/cmms-field-extractor-training.md`
- Modify: `tests/test_cmms_field_extractor_training_data.py`

- [ ] **Step 1: Add failing documentation tests**

Append these tests:

```python
class CmmsFieldExtractorTrainingDocsTests(unittest.TestCase):
    def test_modelfile_example_names_base_and_adapter(self) -> None:
        modelfile = ROOT / "training" / "cmms_field_extractor" / "Modelfile.example"
        text = modelfile.read_text(encoding="utf-8")

        self.assertIn("FROM", text)
        self.assertIn("ADAPTER", text)
        self.assertIn("cmms-field-extractor-qwen3-8b-lora-v1", text)

    def test_training_runbook_covers_eval_ollama_and_rollback(self) -> None:
        doc = ROOT / "docs" / "cmms-field-extractor-training.md"
        text = doc.read_text(encoding="utf-8")

        self.assertIn("python -m unittest", text)
        self.assertIn("ollama create cmms-field-extractor-qwen3-8b-lora-v1", text)
        self.assertIn("EXTRACTOR_MODEL_NAME", text)
        self.assertIn("rollback", text.lower())
        self.assertIn("locked test", text.lower())
```

- [ ] **Step 2: Run the failing documentation tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorTrainingDocsTests -v
```

Expected: FAIL because the Modelfile and runbook do not exist yet.

- [ ] **Step 3: Add Ollama Modelfile example**

Create `training/cmms_field_extractor/Modelfile.example`:

```text
# Example Ollama Modelfile for CMMS field extractor v1.
# Replace paths with local GGUF files produced by the export step.

FROM ./qwen3-8b-instruct.Q4_K_M.gguf
ADAPTER ./cmms-field-extractor-qwen3-8b-lora-v1.gguf

PARAMETER temperature 0
PARAMETER top_p 0.9

SYSTEM """
Extract CMMS work request fields. Return strict JSON only. Never claim a work order was created.
"""
```

- [ ] **Step 4: Add training runbook**

Create `docs/cmms-field-extractor-training.md`:

```markdown
# CMMS Field Extractor Training Runbook

This runbook describes the local-only path for preparing, evaluating, training, importing, and rolling back `cmms-field-extractor-qwen3-8b-lora-v1`.

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
- Hallucinated building or room rate at most 2 percent.
- Unsafe work-order-created claims equal 0.
- Validator bypass attempts equal 0.

## Ollama Import

After exporting the model or adapter to GGUF, create the local model:

```powershell
ollama create cmms-field-extractor-qwen3-8b-lora-v1 -f training/cmms_field_extractor/Modelfile
```

Set the extractor route to the candidate:

```dotenv
EXTRACTOR_MODEL_NAME=cmms-field-extractor-qwen3-8b-lora-v1
```

Leave `OLLAMA_MODEL` unchanged unless every model call should move to a new default.

## Rollback

To rollback, unset `EXTRACTOR_MODEL_NAME` or set it back to `qwen3:8b`, then restart the API process. The previous model remains available because extractor selection is configuration-only.
```

- [ ] **Step 5: Run documentation tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data.CmmsFieldExtractorTrainingDocsTests -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add training/cmms_field_extractor/Modelfile.example docs/cmms-field-extractor-training.md tests/test_cmms_field_extractor_training_data.py
git commit -m "Document CMMS extractor training and Ollama import"
```

---

### Task 9: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run all focused tests**

Run:

```powershell
python -m unittest tests.test_cmms_field_extractor_training_data tests.test_cmms_field_extractor_eval tests.test_extractor_model_config -v
```

Expected: PASS.

- [ ] **Step 2: Run safety and intake regression tests**

Run:

```powershell
python -m unittest tests.test_fast_mode_intake_api tests.test_code_normalizer_intake_api tests.test_safety_reviewer tests.test_cmms_auto_push tests.test_cmms_handoff_candidate -v
```

Expected: PASS.

- [ ] **Step 3: Inspect changed files**

Run:

```powershell
git status --short
git diff --stat HEAD
```

Expected: only files from this plan are changed.

- [ ] **Step 4: Commit any final fixups**

If verification required small fixes, commit them:

```powershell
git add <fixed-files>
git commit -m "Verify CMMS extractor training pipeline"
```

Expected: no uncommitted plan-related changes remain.

---

## Self-Review Notes

- Spec coverage: data policy, anonymization, deterministic split, QLoRA training skeleton, evaluator gates, Ollama import, extractor-only model routing, rollback, and safety boundaries are each mapped to tasks.
- Scope: this plan does not train a model during normal app tests and does not add CMMS write, approval, email, generic chat, or direct Ollama exposure.
- Risk control: large datasets, safetensors, GGUF files, and model artifacts are ignored by git; locked-test policy is documented and evaluated.
- Testing: each implementation task starts with a failing unittest and ends with a focused command plus commit.
