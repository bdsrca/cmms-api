import importlib
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class ExtractorModelConfigTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        os.environ.pop("OLLAMA_MODEL", None)
        os.environ.pop("EXTRACTOR_MODEL_NAME", None)

    def test_extractor_model_defaults_to_global_model(self) -> None:
        os.environ.pop("OLLAMA_MODEL", None)
        os.environ.pop("EXTRACTOR_MODEL_NAME", None)

        import app.config as config

        importlib.reload(config)
        self.assertEqual(config.MODEL_NAME, "qwen3:8b")
        self.assertEqual(config.EXTRACTOR_MODEL_NAME, "qwen3:8b")

    def test_extractor_model_can_be_overridden_without_changing_global_model(self) -> None:
        os.environ["OLLAMA_MODEL"] = "qwen3:8b"
        os.environ["EXTRACTOR_MODEL_NAME"] = "cmms-field-extractor-qwen3-8b-lora-v1"

        import app.config as config

        importlib.reload(config)
        self.assertEqual(config.MODEL_NAME, "qwen3:8b")
        self.assertEqual(
            config.EXTRACTOR_MODEL_NAME,
            "cmms-field-extractor-qwen3-8b-lora-v1",
        )

    def test_call_extractor_model_uses_extractor_model_name(self) -> None:
        import app.ai_endpoints as ai_endpoints

        with patch.object(ai_endpoints, "EXTRACTOR_MODEL_NAME", "cmms-field-extractor-qwen3-8b-lora-v1"):
            self.assertEqual(
                ai_endpoints.extractor_model_name(),
                "cmms-field-extractor-qwen3-8b-lora-v1",
            )

    async def test_extract_work_order_fields_passes_extractor_model_to_ollama(self) -> None:
        import app.ai_endpoints as ai_endpoints

        captured: dict[str, str] = {}

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            captured["model"] = model
            return (
                '{"request_type":"HVAC",'
                '"building":"ARC",'
                '"room":"205",'
                '"priority":"NORMAL",'
                '"summary":"AC noise in room 205",'
                '"missing_fields":[],'
                '"needs_human_review":false,'
                '"confidence":0.9}'
            )

        payload = SimpleNamespace(
            text="AC noise in ARC room 205",
            environment_code=None,
            valid_buildings=["ARC"],
            valid_priorities=["NORMAL"],
        )

        with patch.object(ai_endpoints, "EXTRACTOR_MODEL_NAME", "cmms-field-extractor-qwen3-8b-lora-v1"):
            result = await ai_endpoints.extract_work_order_fields(payload, call_ollama_func=fake_call_ollama)

        self.assertEqual(captured["model"], "cmms-field-extractor-qwen3-8b-lora-v1")
        self.assertEqual(result["building"], "ARC")
