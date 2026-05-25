from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ApiSampleCallsDocsTests(unittest.TestCase):
    def test_api_sample_calls_document_covers_client_endpoints(self) -> None:
        docs = read("docs/api-sample-calls.md")

        self.assertIn("# API Sample Calls", docs)
        self.assertIn("POST /api/ai/cmms-intake", docs)
        self.assertIn("POST /api/ai/intake/email", docs)
        self.assertIn("POST /api/ai/cmms-assistant", docs)
        self.assertIn("POST /api/ai/extract-work-order-fields", docs)
        self.assertIn("POST /api/ai/summarize-work-order", docs)
        self.assertIn("x-api-key: $LLM_API_KEY", docs)
        self.assertIn("Advisory only", docs)

    def test_api_sample_calls_document_includes_language_examples(self) -> None:
        docs = read("docs/api-sample-calls.md")

        self.assertIn("## Language Examples", docs)
        self.assertIn("### curl", docs)
        self.assertIn("### PowerShell", docs)
        self.assertIn("### JavaScript fetch", docs)
        self.assertIn("### Python requests", docs)
        self.assertIn("API_SAMPLE_ENDPOINT", docs)
        self.assertIn("## Export Package", docs)
        self.assertIn("CMMS Local AI API Quick Docs", docs)

    def test_api_builder_exposes_language_dropdown_for_generated_examples(self) -> None:
        html = read("app/ui.py")

        self.assertIn('id="bLanguage"', html)
        self.assertIn('<option value="curl">curl</option>', html)
        self.assertIn('<option value="powershell">PowerShell</option>', html)
        self.assertIn('<option value="javascript">JavaScript fetch</option>', html)
        self.assertIn('<option value="python">Python requests</option>', html)
        self.assertIn("function builderLanguageExamples(uri, body, apiKey, includeValidation)", html)
        self.assertIn("Generated example:", html)


if __name__ == "__main__":
    unittest.main()
