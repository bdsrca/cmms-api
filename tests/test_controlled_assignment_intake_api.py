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


class ControlledAssignmentIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "controlled-assignment-test-key"
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()

    def tearDown(self) -> None:
        app_main.app.dependency_overrides.pop(current_user, None)
        self.db_patcher.stop()
        self.tmp.cleanup()

    def import_assignment_codes(self) -> None:
        import_code_rows(
            "DEFAULT",
            "assign_to",
            [{"code": "Nina Night", "label": "Nina Night", "aliases": "", "metadata_json": ""}],
            replace=True,
        )
        import_code_rows(
            "DEFAULT",
            "issue_to_employee_number",
            [{"code": "100", "label": "100", "aliases": "", "metadata_json": ""}],
            replace=True,
        )
        import_code_rows(
            "DEFAULT",
            "technician_roster",
            [
                {
                    "code": "TECH-100",
                    "label": "Nina Night",
                    "aliases": "Nina",
                    "metadata_json": json.dumps(
                        {
                            "shift": "night",
                            "trades": ["HVAC"],
                            "assign_to": "Nina Night",
                            "issue_to": "100",
                            "job_type": "Maintenance",
                        }
                    ),
                }
            ],
            replace=True,
        )

    def fake_ollama(self):
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
                        "summary": "AHU-3 needs filters checked tonight.",
                    }
                )
            if "Code Normalization Suggestion Agent" in system:
                return json.dumps({"suggestions": []})
            if "Generate advisory CMMS draft text only" in system:
                context = json.loads(messages[1]["content"])
                self.assertEqual(context["assignment_context"]["assignment"]["assign_to"], "Nina Night")
                self.assertEqual(context["action_plan"]["actions"][1]["assignment"]["issue_to"], "100")
                return json.dumps(
                    {
                        "draft_wo_description": "Inspect AHU-3 filters. Assignment is prepared for Nina Night.",
                        "internal_note": "On-duty technician resolved from configured roster.",
                        "client_reply": "Thanks, we captured the AHU-3 request for review.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps({"status": "pass", "human_review_recommended": False, "risk_flags": [], "notes": []})
            raise AssertionError(system)

        return fake_call_ollama

    def test_cmms_intake_applies_resolved_on_duty_assignment_to_result(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            self.import_assignment_codes()
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "controlled-assignment-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3 and assign it to tonight's on-duty technician.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "full",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["assignment_context"]["status"], "resolved")
        self.assertEqual(data["assignment_context"]["technician"]["code"], "TECH-100")
        self.assertEqual(data["result"]["assign_to"], "Nina Night")
        self.assertEqual(data["result"]["issue_to"], "100")
        self.assertEqual(data["result"]["job_type"], "Maintenance")
        self.assertEqual(data["action_plan"]["actions"][0]["action_id"], "create_work_order")
        self.assertEqual(data["action_plan"]["actions"][1]["action_id"], "assign_work_order")
        self.assertEqual(data["action_plan"]["actions"][1]["assignment"]["assign_to"], "Nina Night")

    def test_trace_records_assignment_and_action_plan_before_contract_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()
        app_main.app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with TestClient(app_main.app) as client:
            self.import_assignment_codes()
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "controlled-assignment-test-key"},
                json={
                    "text": "Create a high priority work order for AHU-3 and assign it to tonight's on-duty technician.",
                    "environment_code": "DEFAULT",
                    "workflow_mode": "full",
                },
            )
            trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")

        self.assertEqual(trace.status_code, 200, trace.text)
        names = [step["step_name"] for step in trace.json()["steps"]]
        self.assertIn("assignment_resolution", names)
        self.assertIn("action_plan_composed", names)
        self.assertLess(names.index("work_order_planning"), names.index("assignment_resolution"))
        self.assertLess(names.index("assignment_resolution"), names.index("action_plan_composed"))
        self.assertLess(names.index("action_plan_composed"), names.index("output_contract_validation"))


if __name__ == "__main__":
    unittest.main()
