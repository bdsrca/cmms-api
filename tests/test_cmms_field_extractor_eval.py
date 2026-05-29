import unittest

from training.cmms_field_extractor.evaluate import evaluate_predictions
from training.cmms_field_extractor.run_ollama_eval import (
    DEFAULT_SYSTEM_PROMPT,
    build_eval_example,
    build_ollama_chat_payload,
    prompt_messages_from_record,
)


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
        self.assertEqual(
            report["per_field_accuracy"],
            {
                "building": 1.0,
                "priority": 1.0,
                "request_type": 1.0,
                "room": 1.0,
                "summary": 1.0,
            },
        )
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


class CmmsFieldExtractorOllamaEvalRunnerTests(unittest.TestCase):
    def test_default_eval_prompt_includes_college_context(self) -> None:
        prompt = DEFAULT_SYSTEM_PROMPT.lower()

        self.assertIn("college", prompt)
        self.assertIn("campus", prompt)

    def test_prompt_messages_excludes_expected_assistant_payload(self) -> None:
        record = {
            "messages": [
                {"role": "system", "content": "Extract fields."},
                {"role": "user", "content": "Leak in A101"},
                {"role": "assistant", "content": '{"building":"A","room":"101"}'},
            ]
        }

        self.assertEqual(
            prompt_messages_from_record(record),
            [
                {"role": "system", "content": "Extract fields."},
                {"role": "user", "content": "Leak in A101"},
            ],
        )

    def test_prompt_messages_can_replace_system_prompt_with_strict_schema(self) -> None:
        record = {
            "messages": [
                {"role": "system", "content": "Loose prompt."},
                {"role": "user", "content": "Leak in A101"},
                {"role": "assistant", "content": '{"building":"A","room":"101"}'},
            ]
        }

        self.assertEqual(
            prompt_messages_from_record(record, system_prompt="Strict schema."),
            [
                {"role": "system", "content": "Strict schema."},
                {"role": "user", "content": "Leak in A101"},
            ],
        )

    def test_build_eval_example_uses_assistant_payload_as_expected(self) -> None:
        record = {
            "messages": [
                {"role": "system", "content": "Extract fields."},
                {"role": "user", "content": "Leak in A101"},
                {"role": "assistant", "content": '{"building":"A","room":"101"}'},
            ]
        }

        example = build_eval_example(record, example_id="sample-1", prediction="{}")

        self.assertEqual(example["id"], "sample-1")
        self.assertEqual(example["expected"], {"building": "A", "room": "101"})
        self.assertEqual(example["prediction"], "{}")

    def test_build_ollama_chat_payload_requests_json_and_temperature_zero(self) -> None:
        payload = build_ollama_chat_payload(
            model="phi4-mini:latest",
            messages=[{"role": "user", "content": "Leak in A101"}],
        )

        self.assertEqual(payload["model"], "phi4-mini:latest")
        self.assertEqual(payload["format"], "json")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["temperature"], 0)
