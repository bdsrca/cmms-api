import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiApiKeyMemoryTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_operator_api_key_is_remembered_in_browser_storage(self) -> None:
        html = self.portal_source()

        self.assertIn("cmmsOperatorApiKey", html)
        self.assertIn("loadSavedApiKey", html)
        self.assertIn("rememberApiKey", html)
        self.assertIn("forgetApiKey", html)
        self.assertIn("localStorage.getItem", html)
        self.assertIn("localStorage.setItem", html)
        self.assertIn("localStorage.removeItem", html)

    def test_test_email_and_builder_key_inputs_update_saved_key(self) -> None:
        html = self.portal_source()

        self.assertIn('id="tKey"', html)
        self.assertIn('id="eKey"', html)
        self.assertIn('id="bKey"', html)
        self.assertIn('oninput="rememberApiKey(this.value)"', html)
        self.assertIn("Forget key", html)


if __name__ == "__main__":
    unittest.main()
