import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SafetyReviewerPromptCompareUITests(unittest.TestCase):
    def test_reviewer_prompt_detail_exposes_active_vs_candidate_compare(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("compareReviewerPromptAgainstActive(${prompt.id})", html)
        self.assertIn("compareReviewerPromptAgainstActive(reviewerPromptId)", html)
        self.assertIn("renderReviewerPromptCompareSummary", html)
        self.assertIn("Reviewer prompt comparison", html)

    def test_reviewer_prompt_compare_reuses_suite_runs_without_new_route(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('/api/admin/prompt-versions/cmms-intake-reviewer', html)
        self.assertIn('"reviewer_prompt_id": active.id', html)
        self.assertIn('"reviewer_prompt_id": reviewerPromptId', html)
        self.assertNotIn("/api/admin/reviewer-prompt-comparisons", html)


if __name__ == "__main__":
    unittest.main()
