import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SafetyReviewerPromotionPreviewUITests(unittest.TestCase):
    def test_reviewer_compare_result_can_prefill_override_reason(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("reviewerPromotionPreview", html)
        self.assertIn("renderReviewerPromotionPreview", html)
        self.assertIn("useReviewerPreviewForPromotion()", html)
        self.assertIn("Reviewer smoke preview passed", html)
        self.assertIn("promotionOverrideReason", html)

    def test_reviewer_promotion_preview_does_not_add_backend_gate_route(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("Preview passed; activation still requires admin override", html)
        self.assertNotIn("/api/admin/reviewer-prompt-promotions", html)
        self.assertNotIn("/api/admin/reviewer-prompt-comparisons", html)


if __name__ == "__main__":
    unittest.main()
