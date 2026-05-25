import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodeNormalizerUITests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_test_console_renders_code_normalization_panel(self) -> None:
        html = self.portal_source()

        self.assertIn('collapsiblePanel("Code Normalization"', html)
        self.assertIn('id="tCodeNormalization"', html)
        self.assertIn("function renderCodeNormalization(block)", html)
        self.assertIn("renderCodeNormalization(data.code_normalization);", html)


if __name__ == "__main__":
    unittest.main()
