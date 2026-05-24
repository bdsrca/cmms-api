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


class InventoryProcurementIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "inventory-procurement-test-key"
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
                self.assertEqual(context["inventory_context"]["status"], "shortage")
                self.assertEqual(context["procurement_request"]["status"], "drafted")
                self.assertIn("0 on hand", context["procurement_request"]["reason"])
                return json.dumps(
                    {
                        "draft_wo_description": "Inspect AHU-3 filters and note filter shortage.",
                        "internal_note": "Inventory shows no AHU filters on hand; procurement draft prepared.",
                        "client_reply": "Thanks, we captured the AHU-3 request for review.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps({"status": "pass", "human_review_recommended": False, "risk_flags": [], "notes": []})
            raise AssertionError(system)

        return fake_call_ollama

    def test_cmms_intake_returns_inventory_context_and_procurement_request(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "inventory-procurement-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3, assign it to tonight's on-duty technician, check inventory for filters, and create a purchase request if none are available.",
                    "environment_code": "DEFAULT",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["inventory_context"]["status"], "shortage")
        self.assertTrue(data["inventory_context"]["requires_procurement"])
        self.assertEqual(data["procurement_request"]["status"], "drafted")
        self.assertEqual(data["procurement_request"]["lines"][0]["part_number"], "FILTER-AHU-20X25X2")
        self.assertEqual(data["action_plan"]["actions"][2]["action_id"], "create_purchase_request")
        self.assertEqual(data["action_plan"]["actions"][2]["status"], "dry_run")
        self.assertIn("0 on hand", data["procurement_request"]["reason"])

    def test_trace_records_inventory_and_procurement_before_contract_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()
        app_main.app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with TestClient(app_main.app) as client:
            seed_demo_environment("DEFAULT")
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "inventory-procurement-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3, assign it to tonight's on-duty technician, check inventory for filters, and create a purchase request if none are available.",
                    "environment_code": "DEFAULT",
                },
            )
            trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")

        self.assertEqual(trace.status_code, 200, trace.text)
        names = [step["step_name"] for step in trace.json()["steps"]]
        self.assertIn("inventory_check", names)
        self.assertIn("procurement_planning", names)
        self.assertLess(names.index("work_order_planning"), names.index("inventory_check"))
        self.assertLess(names.index("inventory_check"), names.index("procurement_planning"))
        self.assertLess(names.index("procurement_planning"), names.index("output_contract_validation"))


if __name__ == "__main__":
    unittest.main()
