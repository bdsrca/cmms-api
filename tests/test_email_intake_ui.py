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
        self.assertIn("emailFrom", html)
        self.assertIn("emailTo", html)
        self.assertIn("emailSubmittedBy", html)
        self.assertIn("emailPhone", html)
        self.assertIn("emailDue", html)
        self.assertIn("emailLocationRaw", html)
        self.assertIn("emailBuilding", html)
        self.assertIn("emailRoom", html)
        self.assertIn("emailSubject", html)
        self.assertIn("emailBody", html)
        self.assertIn("handleEmailImport", html)
        self.assertIn("/api/ai/intake/email", html)
        self.assertIn("from_email", html)
        self.assertIn("to_email", html)
        self.assertIn("requested_due_at", html)
        self.assertIn("submitted_phone", html)
        test_panel = html.split("function renderTestInputPanel()", 1)[1].split("function renderTestModeHelp()", 1)[0]
        self.assertNotIn("emailFrom", test_panel)
        self.assertNotIn("runTest('email_paste')", test_panel)
        self.assertNotIn("Future mailbox reading is reserved", html)
        self.assertNotIn("does not connect to a mailbox", html)
        self.assertNotIn("Paste the email body here", html)


if __name__ == "__main__":
    unittest.main()
