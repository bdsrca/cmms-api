import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntakeMetadataUITests(unittest.TestCase):
    def test_test_console_extracts_metadata_from_content(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        test_panel = html.split("function renderTestInputPanel()", 1)[1].split("function renderTestModeHelp()", 1)[0]
        self.assertNotIn("testSubmittedBy", test_panel)
        self.assertNotIn("testSubmittedEmail", test_panel)
        self.assertNotIn("testSubmittedPhone", test_panel)
        self.assertNotIn("testDue", test_panel)
        self.assertNotIn("testLocationRaw", test_panel)
        self.assertNotIn("testBuilding", test_panel)
        self.assertNotIn("testRoom", test_panel)
        self.assertNotIn("buildTestIntakeMetadata", html)

    def test_api_builder_cmms_intake_payload_uses_content_only(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        builder = html.split("function builderRequestBody(endpoint)", 1)[1].split("function endpointDoc", 1)[0]
        self.assertNotIn("bodyObj.submission", builder)
        self.assertNotIn("bodyObj.request", builder)
        self.assertNotIn("requested_due_at", builder)

    def test_response_surface_renders_intake_metadata_panel(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(html.count('id="tMetadata"'), 2)
        self.assertIn("function renderIntakeMetadata(data)", html)
        self.assertIn("Submitted by", html)
        self.assertIn("Requested due", html)
        self.assertIn("renderIntakeMetadata(data);", html)

    def test_metadata_panel_supports_operator_review_corrections(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("metadataSubmittedBy", html)
        self.assertIn('type="date" id="metadataDue"', html)
        self.assertIn("applyMetadataReview()", html)
        self.assertIn("resetMetadataReview()", html)
        self.assertIn("function applyMetadataReview()", html)
        self.assertIn("state.lastTestResponse", html)
        self.assertIn('setConsoleOutput("tOut", data);', html)

    def test_metadata_review_marks_reviewed_and_corrected_fields(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("metadata_review", html)
        self.assertIn("/metadata-review/apply", html)
        self.assertIn("JSON.stringify(patch)", html)
        self.assertIn("data.metadata_review = review.metadata_review", html)


if __name__ == "__main__":
    unittest.main()
