import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EmailIntakeUITests(unittest.TestCase):
    def test_ui_exposes_email_as_dedicated_menu_page(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("email_paste", html)
        self.assertIn("email_mailbox", html)
        self.assertIn('"email","Email Intake"', html)
        self.assertIn("function emailIntake()", html)
        self.assertIn("emailIntake", html)
        email_page = html.split("function emailIntake()", 1)[1].split("function renderTestInputPanel()", 1)[0]
        email_runner = html.split("async function runEmailIntake()", 1)[1].split("function setVoiceSample", 1)[0]
        self.assertIn("emailFrom", html)
        self.assertIn("emailTo", html)
        self.assertNotIn("emailSubmittedBy", email_page)
        self.assertNotIn("emailPhone", email_page)
        self.assertNotIn("emailDue", email_page)
        self.assertNotIn("emailLocationRaw", email_page)
        self.assertNotIn("emailBuilding", email_page)
        self.assertNotIn("emailRoom", email_page)
        self.assertIn("emailSubject", html)
        self.assertIn("emailBody", html)
        self.assertIn("handleEmailImport", html)
        self.assertIn("/api/ai/intake/email", html)
        self.assertIn("from_email", html)
        self.assertIn("to_email", html)
        self.assertNotIn("requested_due_at", html)
        self.assertNotIn("submitted_phone", email_runner)
        test_panel = html.split("function renderTestInputPanel()", 1)[1].split("function renderTestModeHelp()", 1)[0]
        self.assertNotIn("emailFrom", test_panel)
        self.assertNotIn("runTest('email_paste')", test_panel)
        self.assertNotIn("Future mailbox reading is reserved", html)
        self.assertNotIn("does not connect to a mailbox", html)
        self.assertNotIn("Paste the email body here", html)

    def test_email_intake_has_example_request_loader(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")
        email_page = html.split("function emailIntake()", 1)[1].split("function renderTestInputPanel()", 1)[0]

        self.assertIn("setEmailExample()", email_page)
        self.assertIn("Example", email_page)
        self.assertIn("function setEmailExample()", html)
        self.assertIn("resident.services@example.com", html)
        self.assertIn("requested by Priya Shah", html)
        self.assertIn("Unit 205", html)


if __name__ == "__main__":
    unittest.main()
