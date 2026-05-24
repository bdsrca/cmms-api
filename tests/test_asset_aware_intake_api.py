import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
import app.main as app_main
from app.environments import import_code_rows
from app.security import PortalUser, current_user


class AssetAwareIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "asset-aware-intake-test-key"
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()

    def tearDown(self) -> None:
        app_main.app.dependency_overrides.pop(current_user, None)
        self.db_patcher.stop()
        self.tmp.cleanup()

    def import_ahu_asset(self) -> None:
        import_code_rows(
            "DEFAULT",
            "assets",
            [
                {
                    "code": "AHU-3",
                    "label": "Air Handler Unit 3",
                    "aliases": "AHU 3,Air Handler 3",
                    "metadata_json": json.dumps(
                        {
                            "asset_type": "Air Handler Unit",
                            "building": "ARC",
                            "room": "MECH-1",
                            "trade": "HVAC",
                            "work_order_type": "HVAC",
                            "parts": [
                                {
                                    "part_number": "FILTER-AHU-20X25X2",
                                    "description": "20x25x2 AHU filter",
                                    "quantity": 4,
                                    "unit": "EA",
                                }
                            ],
                        }
                    ),
                }
            ],
            replace=True,
        )

    def fake_ollama(self, captured_draft_contexts: list[dict]):
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.93})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "URGENT",
                        "summary": "AHU-3 needs filters checked.",
                    }
                )
            if "Code Normalization Suggestion Agent" in system:
                return json.dumps({"suggestions": []})
            if "Generate advisory CMMS draft text only" in system:
                captured_draft_contexts.append(json.loads(messages[1]["content"]))
                return json.dumps(
                    {
                        "draft_wo_description": "Inspect AHU-3 filters. Asset context resolved for planning only.",
                        "internal_note": "Asset AHU-3 resolved; likely filters are planning hints only.",
                        "client_reply": "Thanks, we captured the AHU-3 filter request for review.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps({"status": "pass", "human_review_recommended": False, "risk_flags": [], "notes": []})
            raise AssertionError(system)

        return fake_call_ollama

    def test_cmms_intake_returns_asset_context_and_work_order_plan(self) -> None:
        captured_draft_contexts: list[dict] = []
        app_main.ai_call_ollama = self.fake_ollama(captured_draft_contexts)

        with TestClient(app_main.app) as client:
            self.import_ahu_asset()
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "asset-aware-intake-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3 and check filters.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "full",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["asset_context"]["status"], "resolved")
        self.assertEqual(data["asset_context"]["asset"]["code"], "AHU-3")
        self.assertEqual(data["work_order_plan"]["status"], "planned")
        self.assertEqual(data["work_order_plan"]["likely_parts"][0]["part_number"], "FILTER-AHU-20X25X2")
        self.assertEqual(captured_draft_contexts[-1]["asset_context"]["asset"]["code"], "AHU-3")
        self.assertEqual(captured_draft_contexts[-1]["work_order_plan"]["asset_code"], "AHU-3")

    def test_workflow_trace_records_asset_resolution_before_contract_validation(self) -> None:
        captured_draft_contexts: list[dict] = []
        app_main.ai_call_ollama = self.fake_ollama(captured_draft_contexts)
        app_main.app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with TestClient(app_main.app) as client:
            self.import_ahu_asset()
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "asset-aware-intake-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3 and check filters.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "full",
                },
            )
            trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")

        self.assertEqual(trace.status_code, 200, trace.text)
        names = [step["step_name"] for step in trace.json()["steps"]]
        self.assertIn("asset_resolution", names)
        self.assertIn("work_order_planning", names)
        self.assertLess(names.index("model_extraction"), names.index("asset_resolution"))
        self.assertLess(names.index("asset_resolution"), names.index("work_order_planning"))
        self.assertLess(names.index("work_order_planning"), names.index("output_contract_validation"))


if __name__ == "__main__":
    unittest.main()
