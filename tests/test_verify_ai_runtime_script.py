from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class VerifyAiRuntimeScriptTests(unittest.TestCase):
    def test_verify_ai_runtime_script_runs_targeted_checks(self) -> None:
        script = (ROOT / "scripts" / "verify_ai_runtime.ps1").read_text(encoding="utf-8")

        self.assertIn("test_ai_runtime_config.py", script)
        self.assertIn("test_extractor_model_config.py", script)
        self.assertIn("test_fast_mode_intake_api.py", script)
        self.assertIn("py_compile", script)


if __name__ == "__main__":
    unittest.main()
