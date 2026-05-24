import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app import ai_endpoints
import app.main as app_main
from app.demo_environment import seed_demo_environment
from app.security import PortalUser, current_user


class FastModeIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "fast-mode-test-key"
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        if hasattr(ai_endpoints, "clear_fast_extraction_cache"):
            ai_endpoints.clear_fast_extraction_cache()

    def tearDown(self) -> None:
        app_main.app.dependency_overrides.pop(current_user, None)
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_fast_mode_uses_single_extraction_call_and_deterministic_post_processing(self) -> None:
        calls: list[str] = []

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            calls.append(system)
            if "Extract CMMS fields from the request" in system:
                return json.dumps(
                    {
                        "request_type": "HVAC",
                        "building": "ARC",
                        "room": "MECH-1",
                        "priority": "URGENT",
                        "summary": "AHU-3 needs filter inspection in ARC mechanical room.",
                        "missing_fields": [],
                        "needs_human_review": False,
                        "confidence": 0.94,
                    }
                )
            raise AssertionError(f"Fast mode should not call this prompt: {system}")

        app_main.ai_call_ollama = fake_call_ollama
        app_main.app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "fast-mode-test-key"},
                json={
                    "text": "Create an urgent work order for AHU-3 in ARC room MECH-1 and assign the on-duty HVAC technician.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "fast",
                },
            )
            trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["workflow_mode"], "fast")
        self.assertEqual(len(calls), 1)
        self.assertEqual(data["code_normalization"]["status"], "skipped")
        self.assertEqual(data["review"]["source"], "fast_mode_deterministic_review")
        self.assertIn("AHU-3", data["drafts"]["draft_wo_description"])

        steps = {step["step_name"]: step for step in trace.json()["steps"]}
        self.assertEqual(steps["code_normalization_suggestion_agent"]["status"], "skipped")
        self.assertEqual(steps["draft_generation"]["model"], None)
        self.assertEqual(steps["safety_reviewer_agent"]["status"], "skipped")
        self.assertEqual(steps["safety_reviewer_agent"]["model"], None)

    def test_fast_mode_reuses_canonical_cache_for_similar_request_text(self) -> None:
        calls: list[str] = []

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            calls.append(system)
            if "Extract CMMS fields from the request" in system:
                return json.dumps(
                    {
                        "request_type": "HVAC",
                        "building": "ARC",
                        "room": "MECH-1",
                        "priority": "URGENT",
                        "summary": "AHU-3 urgent filter inspection in ARC MECH-1.",
                        "missing_fields": [],
                        "needs_human_review": False,
                        "confidence": 0.94,
                    }
                )
            raise AssertionError(system)

        app_main.ai_call_ollama = fake_call_ollama

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            first = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "fast-mode-test-key"},
                json={
                    "text": "Create urgent work order for AHU-3 in ARC room MECH-1.",
                    "environment_code": "DEFAULT",
                },
            )
            second = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "fast-mode-test-key"},
                json={
                    "text": "urgent WO, ARC MECH 1, AHU 3 - create!",
                    "environment_code": "DEFAULT",
                },
            )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first.json()["fast_cache"]["status"], "miss")
        self.assertEqual(second.json()["fast_cache"]["status"], "hit")
        self.assertEqual(second.json()["fast_cache"]["match"], "canonical")
        self.assertEqual(second.json()["workflow_mode"], "fast")

    def test_fast_mode_canonical_cache_misses_when_key_entities_change(self) -> None:
        calls: list[str] = []

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            user = messages[1]["content"] if len(messages) > 1 else ""
            calls.append(user)
            asset = "AHU-4" if "AHU-4" in user else "AHU-3"
            return json.dumps(
                {
                    "request_type": "HVAC",
                    "building": "ARC",
                    "room": "MECH-1",
                    "priority": "URGENT",
                    "summary": f"{asset} urgent filter inspection in ARC MECH-1.",
                    "missing_fields": [],
                    "needs_human_review": False,
                    "confidence": 0.94,
                }
            )

        app_main.ai_call_ollama = fake_call_ollama

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            first = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "fast-mode-test-key"},
                json={
                    "text": "Create urgent work order for AHU-3 in ARC room MECH-1.",
                    "environment_code": "DEFAULT",
                },
            )
            second = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "fast-mode-test-key"},
                json={
                    "text": "Create urgent work order for AHU-4 in ARC room MECH-1.",
                    "environment_code": "DEFAULT",
                },
            )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(first.json()["fast_cache"]["status"], "miss")
        self.assertEqual(second.json()["fast_cache"]["status"], "miss")
        self.assertIn("AHU-4", second.json()["result"]["summary"])

    def test_cmms_intake_defaults_to_fast_when_workflow_mode_is_omitted(self) -> None:
        calls: list[str] = []

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            calls.append(system)
            if "Extract CMMS fields from the request" in system:
                return json.dumps(
                    {
                        "request_type": "HVAC",
                        "building": "ARC",
                        "room": "MECH-1",
                        "priority": "URGENT",
                        "summary": "AHU-3 needs filter inspection in ARC mechanical room.",
                        "missing_fields": [],
                        "needs_human_review": False,
                        "confidence": 0.94,
                    }
                )
            raise AssertionError(f"Default CMMS intake mode should be fast, got prompt: {system}")

        app_main.ai_call_ollama = fake_call_ollama

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "fast-mode-test-key"},
                json={
                    "text": "Create an urgent work order for AHU-3 in ARC room MECH-1.",
                    "environment_code": "DEFAULT",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["workflow_mode"], "fast")
        self.assertEqual(len(calls), 1)
        self.assertEqual(data["code_normalization"]["status"], "skipped")
        self.assertEqual(data["review"]["source"], "fast_mode_deterministic_review")


if __name__ == "__main__":
    unittest.main()
