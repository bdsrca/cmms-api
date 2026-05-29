from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class AiRuntimeConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        import app.main as app_main
        from app.security import current_admin

        app_main.app.dependency_overrides.pop(current_admin, None)

    def test_admin_ai_config_exposes_effective_non_secret_settings(self) -> None:
        import app.main as app_main
        from app.security import PortalUser, current_admin

        app_main.app.dependency_overrides[current_admin] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with TestClient(app_main.app) as client:
            response = client.get("/api/admin/ai-config")

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["models"]["default"], "qwen3:8b")
        self.assertIn("classifier", data["models"])
        self.assertIn("draft", data["models"])
        self.assertIn("safety_reviewer", data["switches"])
        self.assertIn("classifier", data["timeouts_seconds"])
        self.assertNotIn("LLM_API_KEY", response.text)

    def test_ai_config_status_warns_when_configured_model_is_missing(self) -> None:
        import app.config as config

        status = config.build_ai_config_status(
            environ={
                "OLLAMA_MODEL": "qwen3:8b",
                "CLASSIFIER_MODEL_NAME": "cmms-classifier:latest",
                "DRAFT_MODEL_NAME": "cmms-draft:latest",
            },
            available_models=["qwen3:8b"],
        )

        warning_text = " ".join(status["warnings"])
        self.assertIn("cmms-classifier:latest", warning_text)
        self.assertIn("cmms-draft:latest", warning_text)

    def test_timeout_and_review_threshold_env_parsing(self) -> None:
        import app.config as config

        environ = {
            "CLASSIFIER_TIMEOUT_SECONDS": "22",
            "EXTRACTOR_TIMEOUT_SECONDS": "44",
            "DRAFT_TIMEOUT_SECONDS": "66",
            "REVIEWER_TIMEOUT_SECONDS": "88",
            "LOW_CONFIDENCE_REVIEW_THRESHOLD": "0.82",
        }

        self.assertEqual(config.classifier_timeout_seconds_from_env(environ), 22)
        self.assertEqual(config.extractor_timeout_seconds_from_env(environ), 44)
        self.assertEqual(config.draft_timeout_seconds_from_env(environ), 66)
        self.assertEqual(config.reviewer_timeout_seconds_from_env(environ), 88)
        self.assertEqual(config.low_confidence_review_threshold_from_env(environ), 0.82)

    def test_workflow_mode_source_reports_global_override(self) -> None:
        import app.ai_endpoints as ai_endpoints

        payload = SimpleNamespace(workflow_mode="full", environment_code=None)

        with patch.object(ai_endpoints, "AI_FAST_MODE_ENABLED", True):
            mode, source = ai_endpoints.workflow_mode_for_payload_with_source(payload)

        self.assertEqual(mode, "fast")
        self.assertEqual(source, "global_override")

    def test_low_confidence_requires_human_review_even_when_fields_are_valid(self) -> None:
        import app.ai_endpoints as ai_endpoints

        with patch.object(ai_endpoints, "LOW_CONFIDENCE_REVIEW_THRESHOLD", 0.75):
            _request_type, confidence, _fields, validation, _context = ai_endpoints.validate_intake(
                "HVAC",
                0.6,
                {
                    "building": "ARC",
                    "room": "205",
                    "priority": "NORMAL",
                    "summary": "AC noise in room 205.",
                },
                ["ARC"],
                ["NORMAL"],
            )

        self.assertEqual(confidence, 0.6)
        self.assertTrue(validation["can_create_work_order"])
        self.assertTrue(validation["needs_human_review"])
        self.assertTrue(any("confidence" in warning.lower() for warning in validation["warnings"]))

    def test_workflow_run_detail_includes_structured_llm_call_events(self) -> None:
        import app.db as db
        from app.workflow_trace import get_workflow_run, record_llm_call_event, start_workflow_run

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with patch.object(db, "DB_FILE", Path(tmp) / "test.db"):
                db.init_db()
                run_id = start_workflow_run("cmms-intake")
                record_llm_call_event(
                    run_id=run_id,
                    agent_name="classifier",
                    model="qwen3:8b",
                    temperature=0.0,
                    response_format="json",
                    timeout_seconds=30,
                    duration_ms=12.5,
                    status="ok",
                    json_parse_status="success",
                )

                run = get_workflow_run(run_id)

        self.assertIsNotNone(run)
        self.assertEqual(run["llm_calls"][0]["agent_name"], "classifier")
        self.assertEqual(run["llm_calls"][0]["model"], "qwen3:8b")
        self.assertEqual(run["llm_calls"][0]["json_parse_status"], "success")


if __name__ == "__main__":
    unittest.main()
