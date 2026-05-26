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
