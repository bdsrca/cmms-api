import unittest

from training.cmms_field_extractor.audit_source_failures import find_source_matches
from training.cmms_field_extractor.enrich_source_metadata import build_source_metadata_row, is_source_clean_row


class SourceFailureAuditTests(unittest.TestCase):
    def test_source_matching_ignores_short_substring_matches(self) -> None:
        matches = find_source_matches(
            "Monthly Exit Sign Activation Testing Ensure the emergency lighting activates automatically.",
            [
                {"wo": "short", "description": "TEST"},
                {
                    "wo": "detailed",
                    "description": "Monthly Exit Sign Activation Testing Ensure the emergency lighting activates automatically.",
                },
            ],
            limit=1,
        )

        self.assertEqual(matches[0]["wo"], "detailed")

    def test_source_metadata_row_marks_multiple_job_type_matches(self) -> None:
        row = build_source_metadata_row(
            chat_row={
                "id": "0",
                "user": "Set up event room and HVAC schedule.",
                "expected": {"request_type": "HVAC", "priority": "P3"},
            },
            source_matches=[
                {"wo": "1", "type": "EVENT", "job_type": "HVAC", "priority": "P3", "building": "CC1", "room": "110"},
                {
                    "wo": "2",
                    "type": "EVENT",
                    "job_type": "SET-TEARDOWN",
                    "priority": "P3",
                    "building": "CC1",
                    "room": "102",
                },
            ],
            job_type_request_map={"HVAC": "HVAC", "SET-TEARDOWN": "General Maintenance"},
        )

        self.assertEqual(row["source_metadata"]["match_status"], "multiple")
        self.assertIn("multiple_source_job_types", row["review_flags"])
        self.assertIn("source_request_type_conflict", row["review_flags"])
        self.assertEqual(row["source_metadata"]["selected"]["job_type"], "HVAC")

    def test_source_clean_filter_rejects_unmatched_and_conflict_rows(self) -> None:
        self.assertTrue(is_source_clean_row({"review_flags": []}))
        self.assertTrue(is_source_clean_row({"review_flags": ["multiple_source_matches"]}))
        self.assertFalse(is_source_clean_row({"review_flags": ["no_source_match"]}))
        self.assertFalse(is_source_clean_row({"review_flags": ["source_request_type_conflict"]}))
        self.assertFalse(is_source_clean_row({"review_flags": ["source_priority_conflict"]}))


if __name__ == "__main__":
    unittest.main()
