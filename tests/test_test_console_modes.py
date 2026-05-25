import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestConsoleModeTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_test_console_mode_selector_includes_email_and_orchestration(self) -> None:
        html = self.portal_source()

        self.assertIn('<option value="intake/email">Email Intake</option>', html)
        self.assertIn('<option value="orchestration-preview">Orchestration Preview</option>', html)

    def test_test_console_routes_email_and_orchestration_to_existing_controlled_paths(self) -> None:
        html = self.portal_source()

        self.assertIn('ep === "intake/email"', html)
        self.assertIn('ep === "orchestration-preview"', html)
        self.assertIn('"/api/ai/intake/email"', html)
        self.assertIn('"/api/ai/cmms-intake"', html)

    def test_test_console_has_simple_mode_specific_fields(self) -> None:
        html = self.portal_source()

        self.assertIn('id="testEmailFields"', html)
        self.assertIn('id="testEmailFrom"', html)
        self.assertIn('id="testEmailTo"', html)
        self.assertIn('id="testEmailSubject"', html)

    def test_test_console_mode_change_updates_visible_controls(self) -> None:
        html = self.portal_source()

        self.assertIn("function updateTestModeUi()", html)
        self.assertIn("updateTestModeUi(); renderTestModeHelp()", html)
        self.assertIn('id="testWorkflowRow"', html)
        self.assertIn('id="testContentLabel"', html)
        self.assertIn('id="runTestBtn"', html)

    def test_email_mode_uses_email_fields_in_request_body(self) -> None:
        html = self.portal_source()

        self.assertIn('from_email: $("testEmailFrom").value', html)
        self.assertIn('to_email: $("testEmailTo").value', html)
        self.assertIn('subject: $("testEmailSubject").value', html)


if __name__ == "__main__":
    unittest.main()
