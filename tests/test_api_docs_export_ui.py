import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ApiDocsExportUiTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_api_builder_exposes_docs_export_controls(self) -> None:
        html = self.portal_source()

        self.assertIn("API Documentation", html)
        self.assertIn("copyApiDocsMarkdown()", html)
        self.assertIn("downloadApiDocsMarkdown()", html)
        self.assertIn("function apiDocsMarkdown()", html)

    def test_workflow_run_create_test_case_uses_editable_modal(self) -> None:
        html = self.portal_source()

        self.assertIn("openCreateTestCaseFromRunModal", html)
        self.assertIn("id=\"runTcExpected\"", html)
        self.assertIn("buildExpectedJsonFromRunTrace", html)
        self.assertIn("saveTestCaseFromRunModal", html)


if __name__ == "__main__":
    unittest.main()
