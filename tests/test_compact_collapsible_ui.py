import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CompactCollapsibleUiTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_ui_has_reusable_collapsible_panels(self) -> None:
        html = self.portal_source()

        self.assertIn("function collapsiblePanel", html)
        self.assertIn("collapsible-panel", html)
        self.assertIn("<details", html)
        self.assertIn("<summary>", html)

    def test_test_and_email_response_sections_are_collapsible(self) -> None:
        html = self.portal_source()

        self.assertIn('collapsiblePanel("Intake Metadata"', html)
        self.assertIn('collapsiblePanel("Safety Review"', html)
        self.assertIn('collapsiblePanel("Workflow Trace"', html)
        self.assertIn('collapsiblePanel("Contract Validation"', html)
        self.assertIn('collapsiblePanel("Environment Validation"', html)
        self.assertIn('collapsiblePanel("Extracted JSON"', html)

    def test_controls_use_compact_rows(self) -> None:
        html = self.portal_source()

        self.assertIn("compact-field-row", html)
        self.assertIn("compact-actions", html)
        self.assertIn("compact-textarea", html)


if __name__ == "__main__":
    unittest.main()
