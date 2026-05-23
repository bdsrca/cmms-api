import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SafetyReviewerUITests(unittest.TestCase):
    def test_test_console_renders_safety_review_panel(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('id="tReview"', html)
        self.assertIn("function renderSafetyReview(review)", html)
        self.assertIn("renderSafetyReview(data.review);", html)
        self.assertIn("Safety Review", html)

    def test_saved_test_case_defaults_include_reviewer_expectations(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")
        expected_builder = html.split("function expectedFromResponse(response)", 1)[1].split("function openSaveCurrentTestCase()", 1)[0]

        self.assertIn("review_status", expected_builder)
        self.assertIn("review_human_review_recommended", expected_builder)
        self.assertIn("review_risk_flags_contains", expected_builder)


if __name__ == "__main__":
    unittest.main()
