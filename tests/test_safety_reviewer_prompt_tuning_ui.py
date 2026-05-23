import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SafetyReviewerPromptTuningUITests(unittest.TestCase):
    def test_reviewer_prompt_detail_exposes_smoke_suite_shortcuts(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("renderReviewerPromptTuningPanel(prompt)", html)
        self.assertIn("Safety Reviewer Smoke Suite", html)
        self.assertIn("ensureReviewerSmokeSuiteFromPrompt()", html)
        self.assertIn("runReviewerSmokeSuiteFromPrompt(${prompt.id})", html)
        self.assertIn("reviewerSmokeStatus", html)

    def test_shortcuts_use_existing_suite_apis(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("/api/admin/test-suites/safety-reviewer-smoke/ensure", html)
        self.assertIn("/api/admin/test-suites/suite_safety_reviewer_smoke/run", html)
        self.assertIn("reviewer_prompt_id", html)


if __name__ == "__main__":
    unittest.main()
