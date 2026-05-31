from pathlib import Path
import os
import unittest

from training.cmms_field_extractor.schema import (
    REQUIRED_ASSISTANT_KEYS,
    SUMMARY_MAX_CHARS,
    assistant_payload_errors,
    validate_chat_record,
)
from training.cmms_field_extractor.split import split_records
from training.cmms_field_extractor.anonymize import (
    SecretDetectedError,
    build_chat_record,
    normalize_expected_payload,
    reject_if_sensitive,
)


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
        self.assertIn("data/*", gitignore)
        self.assertIn("!data/cmms_field_extractor/.gitkeep", gitignore)
        self.assertIn("!data/cmms_field_extractor/README.md", gitignore)


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
            '"asset_hint":null,'
            '"priority":"urgent",'
            '"summary":"Water dripping",'
            '"human_review_recommended":false}'
        )

        self.assertIn("assistant.missing_fields:missing", validate_chat_record(record))

    def test_rejects_extra_assistant_key(self) -> None:
        payload = {
            "request_type": "work_order_request",
            "asset_hint": None,
            "priority": "urgent",
            "summary": "Water dripping",
            "missing_fields": [],
            "human_review_recommended": False,
            "work_order_created": True,
        }

        self.assertIn("assistant.extra:work_order_created", assistant_payload_errors(payload))

    def test_rejects_building_as_model_output(self) -> None:
        payload = {
            "request_type": "work_order_request",
            "building": "North Campus",
            "asset_hint": None,
            "priority": "urgent",
            "summary": "Water dripping",
            "missing_fields": [],
            "human_review_recommended": False,
        }

        self.assertIn("assistant.extra:building", assistant_payload_errors(payload))

    def test_rejects_unsafe_created_claim_in_summary(self) -> None:
        payload = {
            "request_type": "work_order_request",
            "asset_hint": None,
            "priority": "urgent",
            "summary": "Work order created for water leak.",
            "missing_fields": [],
            "human_review_recommended": False,
        }

        self.assertIn("assistant.unsafe_claim:summary", assistant_payload_errors(payload))

    def test_rejects_overlong_summary(self) -> None:
        payload = {
            "request_type": "work_order_request",
            "asset_hint": None,
            "priority": "urgent",
            "summary": "x" * (SUMMARY_MAX_CHARS + 1),
            "missing_fields": [],
            "human_review_recommended": False,
        }

        self.assertIn("assistant.summary:too_long", assistant_payload_errors(payload))


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
                "asset_hint": "",
                "priority": "URGENT",
                "summary": "  Water leak near ceiling.  ",
                "missing_fields": ["building", "room", "priority", "priority"],
                "human_review_recommended": "yes",
            }
        )

        self.assertEqual(
            normalized,
            {
                "request_type": "Work_Order_Request",
                "asset_hint": None,
                "priority": "URGENT",
                "summary": "Water leak near ceiling.",
                "missing_fields": ["priority"],
                "human_review_recommended": True,
            },
        )

    def test_normalizes_summary_to_contract_length(self) -> None:
        long_summary = (
            "Please set up tables, chairs, trash bins, recycling bins, compost bins, "
            "lighting, HVAC, doors, signs, and cleanup for the campus event before noon "
            "with final walkthrough, reset, and extra support after the event ends."
        )

        normalized = normalize_expected_payload(
            {
                "request_type": "General Maintenance",
                "asset_hint": None,
                "priority": "P3",
                "summary": long_summary,
                "missing_fields": [],
                "human_review_recommended": False,
            }
        )

        self.assertLessEqual(len(normalized["summary"]), SUMMARY_MAX_CHARS)
        self.assertEqual(
            normalized["summary"],
            "Please set up tables, chairs, trash bins, recycling bins, compost bins, lighting, HVAC, doors, signs, and cleanup for the campus event before noon with final",
        )

    def test_build_chat_record_returns_valid_record(self) -> None:
        record = build_chat_record(
            user_text="Water leak in room B204 at North Campus.",
            expected={
                "request_type": "work_order_request",
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
        self.assertIn("college", record["messages"][0]["content"].lower())
        self.assertIn("campus", record["messages"][0]["content"].lower())


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


class CmmsFieldExtractorTrainingScriptTests(unittest.TestCase):
    def test_training_script_import_is_dependency_safe(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        self.assertTrue(callable(train_unsloth.main))
        self.assertIn("data_path", train_unsloth.parse_args(["--data-path", "train.jsonl"]).__dict__)

    def test_training_script_defaults_are_8gb_gpu_friendly(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        args = train_unsloth.parse_args(["--data-path", "train.jsonl"])

        self.assertEqual(args.base_model, "unsloth/Qwen3-8B-unsloth-bnb-4bit")
        self.assertEqual(args.max_seq_length, 1024)
        self.assertEqual(args.per_device_train_batch_size, 1)
        self.assertIsNone(args.dataset_num_proc)
        self.assertEqual(args.max_steps, -1)
        self.assertFalse(args.return_logits)
        self.assertFalse(args.disable_unsloth_compile)
        self.assertEqual(args.min_fused_loss_gb, 0.05)

    def test_training_script_can_disable_unsloth_fused_loss(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        args = train_unsloth.parse_args(["--data-path", "train.jsonl", "--return-logits"])

        self.assertTrue(args.return_logits)

    def test_training_script_can_disable_unsloth_compile(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        previous = {
            "UNSLOTH_COMPILE_DISABLE": os.environ.get("UNSLOTH_COMPILE_DISABLE"),
            "TORCHDYNAMO_DISABLE": os.environ.get("TORCHDYNAMO_DISABLE"),
        }
        try:
            args = train_unsloth.parse_args(["--data-path", "train.jsonl", "--disable-unsloth-compile"])
            train_unsloth.configure_unsloth_compile(args.disable_unsloth_compile)

            self.assertTrue(args.disable_unsloth_compile)
            self.assertEqual(os.environ["UNSLOTH_COMPILE_DISABLE"], "1")
            self.assertEqual(os.environ["TORCHDYNAMO_DISABLE"], "1")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_training_script_clamps_fused_loss_target_memory(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        free_bytes = int(0.01 * 1024 * 1024 * 1024)

        self.assertEqual(train_unsloth.fused_loss_target_gb(free_bytes, 0.05), 0.05)

    def test_training_script_skips_unsloth_multiprocess_dataset_prepare(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        self.assertEqual(train_unsloth.sft_dataset_kwargs(), {"skip_prepare_dataset": True})

    def test_training_script_accepts_resume_from_checkpoint(self) -> None:
        import training.cmms_field_extractor.train_unsloth as train_unsloth

        args = train_unsloth.parse_args(
            [
                "--data-path",
                "train.jsonl",
                "--resume-from-checkpoint",
                "models/cmms_field_extractor/college-phi4-v1-lora/checkpoint-514",
            ]
        )

        self.assertEqual(
            args.resume_from_checkpoint,
            "models/cmms_field_extractor/college-phi4-v1-lora/checkpoint-514",
        )


class CmmsFieldExtractorTrainingDocsTests(unittest.TestCase):
    def test_modelfile_example_names_base_and_adapter(self) -> None:
        modelfile = ROOT / "training" / "cmms_field_extractor" / "Modelfile.example"
        text = modelfile.read_text(encoding="utf-8")

        self.assertIn("FROM", text)
        self.assertIn("ADAPTER", text)
        self.assertIn("college-cmms-field-extractor-phi4-v1", text)

    def test_training_runbook_covers_eval_ollama_and_rollback(self) -> None:
        doc = ROOT / "docs" / "cmms-field-extractor-training.md"
        text = doc.read_text(encoding="utf-8")

        self.assertIn("python -m unittest", text)
        self.assertIn("ollama create college-cmms-field-extractor-phi4-v1", text)
        self.assertIn("EXTRACTOR_MODEL_NAME", text)
        self.assertIn("rollback", text.lower())
        self.assertIn("locked test", text.lower())
