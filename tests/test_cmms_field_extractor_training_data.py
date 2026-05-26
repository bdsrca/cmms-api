from pathlib import Path
import unittest

from training.cmms_field_extractor.schema import (
    REQUIRED_ASSISTANT_KEYS,
    assistant_payload_errors,
    validate_chat_record,
)
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
