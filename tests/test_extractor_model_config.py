import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class ExtractorModelConfigTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        os.environ.pop("OLLAMA_MODEL", None)
        os.environ.pop("EXTRACTOR_MODEL_NAME", None)
        os.environ.pop("EXTRACTOR_MODEL_ENABLED", None)
        os.environ.pop("CLASSIFIER_MODEL_ENABLED", None)
        os.environ.pop("CLASSIFIER_MODEL_NAME", None)
        os.environ.pop("DRAFT_MODEL_ENABLED", None)
        os.environ.pop("DRAFT_MODEL_NAME", None)
        os.environ.pop("SAFETY_REVIEWER_ENABLED", None)
        os.environ.pop("AI_FAST_MODE_ENABLED", None)
        os.environ.pop("OLLAMA_JSON_FORMAT_ENABLED", None)

    def test_extractor_model_defaults_to_global_model(self) -> None:
        import app.config as config

        self.assertEqual(config.model_name_from_env({}), "qwen3:8b")
        self.assertEqual(config.extractor_model_name_from_env({}), "qwen3:8b")

    def test_extractor_model_can_be_overridden_without_changing_global_model(self) -> None:
        import app.config as config

        environ = {
            "OLLAMA_MODEL": "qwen3:8b",
            "EXTRACTOR_MODEL_NAME": "cmms-field-extractor-qwen3-8b-lora-v1",
        }

        self.assertEqual(config.model_name_from_env(environ), "qwen3:8b")
        self.assertEqual(
            config.extractor_model_name_from_env(environ),
            "cmms-field-extractor-qwen3-8b-lora-v1",
        )

    def test_extractor_model_switch_can_disable_override(self) -> None:
        import app.config as config

        environ = {
            "OLLAMA_MODEL": "qwen3:8b",
            "EXTRACTOR_MODEL_NAME": "cmms-field-extractor-qwen3-8b-lora-v1",
            "EXTRACTOR_MODEL_ENABLED": "false",
        }

        self.assertEqual(config.extractor_model_name_from_env(environ), "qwen3:8b")

    def test_classifier_and_draft_model_switches_can_override_or_fallback(self) -> None:
        import app.config as config

        environ = {
            "OLLAMA_MODEL": "qwen3:8b",
            "CLASSIFIER_MODEL_NAME": "cmms-classifier:latest",
            "DRAFT_MODEL_NAME": "cmms-draft-writer:latest",
        }

        self.assertEqual(config.classifier_model_name_from_env(environ), "cmms-classifier:latest")
        self.assertEqual(config.draft_model_name_from_env(environ), "cmms-draft-writer:latest")

        environ["CLASSIFIER_MODEL_ENABLED"] = "false"
        environ["DRAFT_MODEL_ENABLED"] = "off"

        self.assertEqual(config.classifier_model_name_from_env(environ), "qwen3:8b")
        self.assertEqual(config.draft_model_name_from_env(environ), "qwen3:8b")

    def test_runtime_feature_switches_parse_boolean_values(self) -> None:
        import app.config as config

        self.assertFalse(config.safety_reviewer_enabled_from_env({"SAFETY_REVIEWER_ENABLED": "no"}))
        self.assertTrue(config.ai_fast_mode_enabled_from_env({"AI_FAST_MODE_ENABLED": "1"}))
        self.assertFalse(config.ollama_json_format_enabled_from_env({"OLLAMA_JSON_FORMAT_ENABLED": "false"}))

    def test_global_fast_mode_switch_defaults_intake_to_fast(self) -> None:
        from types import SimpleNamespace

        import app.ai_endpoints as ai_endpoints

        payload = SimpleNamespace(workflow_mode=None, environment_code=None)

        with patch.object(ai_endpoints, "AI_FAST_MODE_ENABLED", True):
            self.assertEqual(ai_endpoints.workflow_mode_for_payload(payload), "fast")

    def test_ollama_json_format_switch_can_disable_response_format_payload(self) -> None:
        import app.ai_endpoints as ai_endpoints

        with patch.object(ai_endpoints, "OLLAMA_JSON_FORMAT_ENABLED", False):
            self.assertIsNone(ai_endpoints.ollama_response_format("json"))

    def test_disabled_safety_reviewer_block_marks_reviewer_skipped(self) -> None:
        import app.ai_endpoints as ai_endpoints

        review = ai_endpoints.disabled_reviewer_block()

        self.assertFalse(review["enabled"])
        self.assertTrue(review["reviewer_skipped"])
        self.assertEqual(review["status"], "skipped")

    def test_call_extractor_model_uses_extractor_model_name(self) -> None:
        import app.ai_endpoints as ai_endpoints

        with patch.object(ai_endpoints, "EXTRACTOR_MODEL_NAME", "cmms-field-extractor-qwen3-8b-lora-v1"):
            self.assertEqual(
                ai_endpoints.extractor_model_name(),
                "cmms-field-extractor-qwen3-8b-lora-v1",
            )

    def test_default_field_extraction_prompts_include_college_context(self) -> None:
        import json

        import app.config as config

        standalone_prompt = config.DEFAULT_PROMPT_VERSIONS["extract-work-order-fields"]["system_prompt"].lower()
        intake_prompts = json.loads(config.DEFAULT_PROMPT_VERSIONS["cmms-intake"]["system_prompt"])
        intake_field_prompt = intake_prompts["field_extractor"].lower()

        for prompt in (standalone_prompt, intake_field_prompt):
            self.assertIn("college", prompt)
            self.assertIn("campus", prompt)

    async def test_extract_work_order_fields_passes_extractor_model_to_ollama(self) -> None:
        import app.ai_endpoints as ai_endpoints

        captured: dict[str, str | None] = {}

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b", response_format=None):
            captured["model"] = model
            captured["response_format"] = response_format
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
        self.assertEqual(captured["response_format"], "json")
        self.assertEqual(result["building"], "ARC")

    async def test_main_call_ollama_forwards_response_format(self) -> None:
        import app.main as main

        captured: dict[str, str | None] = {}

        async def fake_ai_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b", response_format=None):
            captured["response_format"] = response_format
            return "{}"

        with patch.object(main, "ai_call_ollama", fake_ai_call_ollama):
            result = await main.call_ollama([{"role": "user", "content": "extract"}], response_format="json")

        self.assertEqual(result, "{}")
        self.assertEqual(captured["response_format"], "json")
