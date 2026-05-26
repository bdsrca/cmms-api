from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CmmsFieldExtractorTrainingDataPolicyTests(unittest.TestCase):
    def test_training_data_directory_documents_local_only_policy(self) -> None:
        readme = ROOT / "data" / "cmms_field_extractor" / "README.md"

        self.assertTrue(readme.exists())
        text = readme.read_text(encoding="utf-8")
        self.assertIn("Do not commit raw CMMS records", text)
        self.assertIn("Do not commit model artifacts", text)
        self.assertIn("anonymized", text.lower())

    def test_gitignore_excludes_training_datasets_and_model_artifacts(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("data/cmms_field_extractor/*.jsonl", gitignore)
        self.assertIn("models/cmms_field_extractor/", gitignore)
        self.assertIn("*.gguf", gitignore)
        self.assertIn("!data/cmms_field_extractor/.gitkeep", gitignore)
        self.assertIn("!data/cmms_field_extractor/README.md", gitignore)
