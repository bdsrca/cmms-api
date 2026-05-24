import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
import app.main as app_main
from app.demo_environment import seed_demo_environment
from app.security import PortalUser, current_user


class OrchestrationSummaryIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "orchestration-summary-test-key"
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()

    def tearDown(self) -> None:
        app_main.app.dependency_overrides.pop(current_user, None)
        self.db_patcher.stop()
        self.tmp.cleanup()

    def fake_ollama(self):
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.94})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "URGENT",
                        "summary": "AHU-3 needs filters checked tonight.",
                    }
                )
            if "Code Normalization Suggestion Agent" in system:
                return json.dumps({"suggestions": []})
            if "Generate advisory CMMS draft text only" in system:
                context = json.loads(messages[1]["content"])
                self.assertEqual(context["orchestration_summary"]["asset_code"], "AHU-3")
                self.assertIn("create_purchase_request", context["orchestration_summary"]["requested_actions"])
                return json.dumps(
                    {
                        "draft_wo_description": "Inspect AHU-3 filters and note filter shortage.",
                        "internal_note": "End-to-end orchestration summary prepared for operator review.",
                        "client_reply": "Thanks, we captured the AHU-3 request for review.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps({"status": "pass", "human_review_recommended": False, "risk_flags": [], "notes": []})
            raise AssertionError(system)

        return fake_call_ollama

    def test_cmms_intake_returns_operator_orchestration_summary(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "orchestration-summary-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3, assign it to tonight's on-duty technician, check filter inventory, and create a purchase request if none are available.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "full",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        summary = data["orchestration_summary"]
        self.assertEqual(summary["schema"], "cmms_orchestration_summary_v1")
        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["asset_code"], "AHU-3")
        self.assertEqual(summary["steps"]["assignment"]["technician"], "Nina Night")
        self.assertEqual(summary["steps"]["inventory"]["status"], "shortage")
        self.assertEqual(summary["steps"]["procurement"]["status"], "dry_run")
        self.assertEqual(summary["cmms_push_status"], "dry_run")
        self.assertIn("create_purchase_request", summary["requested_actions"])
        self.assertIn("AHU-3", summary["operator_message"])
        self.assertEqual(data["result"]["orchestration_summary"]["status"], "dry_run")

    def test_trace_records_orchestration_summary_after_cmms_push(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()
        app_main.app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "orchestration-summary-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3, assign it to tonight's on-duty technician, check filter inventory, and create a purchase request if none are available.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "full",
                },
            )
            trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")

        self.assertEqual(trace.status_code, 200, trace.text)
        names = [step["step_name"] for step in trace.json()["steps"]]
        self.assertIn("orchestration_summary", names)
        self.assertLess(names.index("cmms_auto_push"), names.index("orchestration_summary"))
        summary_step = next(step for step in trace.json()["steps"] if step["step_name"] == "orchestration_summary")
        self.assertEqual(summary_step["output_json"]["status"], "dry_run")
        self.assertIn("create_purchase_request", summary_step["output_json"]["requested_actions"])


if __name__ == "__main__":
    unittest.main()
