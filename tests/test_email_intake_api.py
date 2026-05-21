import unittest
from pathlib import Path

from app.email_intake import build_email_intake_text

ROOT = Path(__file__).resolve().parents[1]


class EmailIntakeApiTests(unittest.TestCase):
    def test_build_email_intake_text_includes_headers_and_body(self) -> None:
        text = build_email_intake_text(
            from_email="tenant@example.com",
            to_email="maintenance@example.com",
            subject="Leak in ARC 205",
            body="Water is leaking under the sink.",
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Email intake",
                    "From: tenant@example.com",
                    "To: maintenance@example.com",
                    "Subject: Leak in ARC 205",
                    "",
                    "Body:",
                    "Water is leaking under the sink.",
                ]
            ),
        )

    def test_build_email_intake_text_trims_whitespace(self) -> None:
        text = build_email_intake_text(
            from_email=" tenant@example.com ",
            to_email=" maintenance@example.com ",
            subject=" Leak in ARC 205 ",
            body="\n Water is leaking under the sink. \n",
        )

        self.assertIn("From: tenant@example.com", text)
        self.assertIn("To: maintenance@example.com", text)
        self.assertIn("Subject: Leak in ARC 205", text)
        self.assertTrue(text.endswith("Water is leaking under the sink."))

    def test_email_intake_endpoint_is_registered_for_email_payloads(self) -> None:
        main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

        self.assertIn('/api/ai/intake/email', main_source)
        self.assertIn("class EmailIntakeRequest", main_source)
        self.assertIn('source="email_api"', main_source)
        self.assertIn("submitted_phone", main_source)
        self.assertIn("requested_due_at", main_source)
        self.assertIn("location: IntakeLocation", main_source)


if __name__ == "__main__":
    unittest.main()
