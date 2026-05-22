import unittest
from pathlib import Path

from app.config import DEFAULT_CMMS_INTAKE_CONTRACT
from app.intake_metadata import build_intake_metadata, extract_metadata_from_text, unreviewed_metadata_review

ROOT = Path(__file__).resolve().parents[1]


class IntakeMetadataTests(unittest.TestCase):
    def test_content_metadata_extracts_contact_and_due_date(self) -> None:
        extracted = extract_metadata_from_text(
            "The air conditioner in ARC room 205 is making loud noise. "
            "My name is Leon, phone is 1234, email address is bdsrca@gmail.com, "
            "I wanted it done by the end of this week.",
            now_func=lambda: "2026-05-21T14:30:00Z",
        )

        self.assertEqual(extracted["submission"]["submitted_by"], "Leon")
        self.assertEqual(extracted["submission"]["submitted_phone"], "1234")
        self.assertEqual(extracted["submission"]["submitted_email"], "bdsrca@gmail.com")
        self.assertEqual(extracted["request"]["requested_due"], "2026-05-22")
        self.assertEqual(extracted["request"]["requested_due_raw"], "by the end of this week")
        self.assertEqual(extracted["request"]["location"]["building"], "ARC")
        self.assertEqual(extracted["request"]["location"]["room"], "205")

    def test_content_metadata_normalizes_common_relative_due_dates(self) -> None:
        cases = [
            ("Please finish this by tomorrow.", "2026-05-22", "by tomorrow"),
            ("Please have it done by next Monday.", "2026-05-25", "by next Monday"),
            ("Please finish it by the end of this month.", "2026-05-31", "by the end of this month"),
        ]

        for content, requested_due, raw in cases:
            with self.subTest(content=content):
                extracted = extract_metadata_from_text(
                    content,
                    now_func=lambda: "2026-05-21T14:30:00Z",
                )

                self.assertEqual(extracted["request"]["requested_due"], requested_due)
                self.assertEqual(extracted["request"]["requested_due_raw"], raw)

    def test_content_metadata_extracts_alternate_contact_and_compact_location_phrases(self) -> None:
        cases = [
            (
                "This is Leon. The fan in ARC 205 keeps rattling. Call me at 416-555-0199.",
                {"submitted_by": "Leon", "submitted_phone": "416-555-0199"},
            ),
            (
                "ARC 205 is too warm. Reach me at leon@example.com.",
                {"submitted_email": "leon@example.com"},
            ),
        ]

        for content, expected_submission in cases:
            with self.subTest(content=content):
                extracted = extract_metadata_from_text(content)

                for key, value in expected_submission.items():
                    self.assertEqual(extracted["submission"][key], value)
                self.assertEqual(extracted["request"]["location"]["building"], "ARC")
                self.assertEqual(extracted["request"]["location"]["room"], "205")

    def test_email_metadata_maps_sender_fallback_and_defaults_method_and_time(self) -> None:
        metadata = build_intake_metadata(
            source="email_api",
            fields={"building": "ARC", "room": "205"},
            submitted_email="tenant@example.com",
            now_func=lambda: "2026-05-21T14:30:00Z",
        )

        self.assertEqual(metadata["submission"]["submitted_email"], "tenant@example.com")
        self.assertEqual(metadata["submission"]["submitted_method"], "email_api")
        self.assertEqual(metadata["submission"]["submitted_at"], "2026-05-21T14:30:00Z")

    def test_content_location_overrides_extracted_location(self) -> None:
        metadata = build_intake_metadata(
            source="manual",
            fields={"building": "BETA", "room": "310"},
            extracted={
                "request": {
                    "location": {"building": "ARC", "room": "205", "area": "North wing", "raw": "ARC 205"}
                }
            },
            now_func=lambda: "2026-05-21T14:30:00Z",
        )

        self.assertEqual(
            metadata["request"]["location"],
            {"building": "ARC", "room": "205", "area": "North wing", "raw": "ARC 205"},
        )
        self.assertTrue(metadata["request"]["location_conflict"])

    def test_requested_due_is_preserved_as_date(self) -> None:
        metadata = build_intake_metadata(
            source="manual",
            fields={"building": "ARC", "room": "205"},
            extracted={"request": {"requested_due": "2026-05-24"}},
            now_func=lambda: "2026-05-21T14:30:00Z",
        )

        self.assertEqual(metadata["request"]["requested_due"], "2026-05-24")

    def test_unreviewed_metadata_review_defaults_for_api_responses(self) -> None:
        self.assertEqual(
            unreviewed_metadata_review(),
            {"reviewed": False, "corrected_fields": []},
        )

    def test_default_contract_allows_submission_and_request_metadata(self) -> None:
        properties = DEFAULT_CMMS_INTAKE_CONTRACT["properties"]

        self.assertIn("submission", properties)
        self.assertIn("request", properties)
        self.assertIn("metadata_review", properties)

    def test_default_output_contract_seed_uses_metadata_version(self) -> None:
        source = (ROOT / "app" / "output_contracts.py").read_text(encoding="utf-8")

        self.assertIn('target_version = "v3"', source)
        self.assertIn("submission metadata", source)


if __name__ == "__main__":
    unittest.main()
