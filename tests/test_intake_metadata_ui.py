import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntakeMetadataUITests(unittest.TestCase):
    def test_test_console_exposes_metadata_for_text_and_voice(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        test_panel = html.split("function renderTestInputPanel()", 1)[1].split("function renderTestModeHelp()", 1)[0]
        self.assertIn("testSubmittedBy", test_panel)
        self.assertIn("testSubmittedEmail", test_panel)
        self.assertIn("testSubmittedPhone", test_panel)
        self.assertIn("testDue", test_panel)
        self.assertIn("testLocationRaw", test_panel)
        self.assertIn("testBuilding", test_panel)
        self.assertIn("testRoom", test_panel)
        self.assertIn("buildTestIntakeMetadata", html)

    def test_api_builder_cmms_intake_payload_includes_metadata(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        builder = html.split("function builderRequestBody(endpoint)", 1)[1].split("function endpointDoc", 1)[0]
        self.assertIn("submission", builder)
        self.assertIn("request", builder)
        self.assertIn("requested_due_at", builder)
        self.assertIn("location", builder)


if __name__ == "__main__":
    unittest.main()
