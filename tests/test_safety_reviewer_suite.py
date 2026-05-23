import unittest
from pathlib import Path

from app.test_suites import safety_reviewer_smoke_definitions

ROOT = Path(__file__).resolve().parents[1]


class SafetyReviewerSmokeSuiteTests(unittest.TestCase):
    def test_smoke_definitions_include_reviewer_assertions(self) -> None:
        suite, cases = safety_reviewer_smoke_definitions("default", required_for_promotion=False)

        self.assertEqual(suite["name"], "Safety Reviewer Smoke Suite")
        self.assertEqual(suite["endpoint"], "cmms-intake")
        self.assertEqual(suite["environment_code"], "DEFAULT")
        self.assertFalse(suite["required_for_promotion"])
        self.assertGreaterEqual(len(cases), 3)
        for case in cases:
            self.assertEqual(case["endpoint"], "cmms-intake")
            self.assertEqual(case["environment_code"], "DEFAULT")
            self.assertIn("review_status", case["expected_json"])
            self.assertIn("review_human_review_recommended", case["expected_json"])

    def test_ensure_route_is_admin_only_and_before_dynamic_suite_route(self) -> None:
        source = (ROOT / "app" / "test_routes.py").read_text(encoding="utf-8")

        ensure_index = source.index('/api/admin/test-suites/safety-reviewer-smoke/ensure')
        dynamic_index = source.index('/api/admin/test-suites/{suite_id}')
        self.assertLess(ensure_index, dynamic_index)
        self.assertIn("PortalUser = Depends(current_admin)", source)

    def test_ui_exposes_smoke_suite_button(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("Safety Reviewer Smoke Suite", html)
        self.assertIn("ensureSafetyReviewerSmokeSuite()", html)
        self.assertIn("/api/admin/test-suites/safety-reviewer-smoke/ensure", html)


if __name__ == "__main__":
    unittest.main()
