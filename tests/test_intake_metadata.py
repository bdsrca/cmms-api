import unittest
from pathlib import Path

from app.config import DEFAULT_CMMS_INTAKE_CONTRACT
from app.intake_metadata import build_intake_metadata, extract_metadata_from_text

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

    def test_default_contract_allows_submission_and_request_metadata(self) -> None:
        properties = DEFAULT_CMMS_INTAKE_CONTRACT["properties"]

        self.assertIn("submission", properties)
        self.assertIn("request", properties)

    def test_default_output_contract_seed_uses_metadata_version(self) -> None:
        source = (ROOT / "app" / "output_contracts.py").read_text(encoding="utf-8")

        self.assertIn('target_version = "v2"', source)
        self.assertIn("submission metadata", source)


if __name__ == "__main__":
    unittest.main()
