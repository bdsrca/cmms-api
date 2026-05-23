import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_main


class SafetyReviewerIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "safety-reviewer-test-key"

    def test_contract_passed_runs_reviewer(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama("pass")

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "safety-reviewer-test-key"},
                json=self.payload(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["review"]["enabled"], True)
        self.assertEqual(data["review"]["status"], "pass")
        self.assertEqual(data["review"]["source"], "safety_reviewer_agent")

    def test_reviewer_warning_does_not_change_deterministic_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama("warning")

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "safety-reviewer-test-key"},
                json=self.payload(),
            )

        data = response.json()
        self.assertEqual(data["review"]["status"], "warning")
        self.assertEqual(data["validation"]["needs_human_review"], False)

    def test_contract_failure_skips_reviewer(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama("raise_if_called")
        contract_failure = {
            "valid": False,
            "errors": [{"field": "summary", "message": "missing"}],
            "warnings": [],
            "contract_version": "v1",
            "normalized_payload": {},
        }

        with patch("app.ai_endpoints.validate_output_contract", return_value=contract_failure):
            with TestClient(app_main.app) as client:
                response = client.post(
                    "/api/ai/cmms-intake",
                    headers={"x-api-key": "safety-reviewer-test-key"},
                    json=self.payload(),
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["review"]["status"], "skipped")

    def payload(self) -> dict:
        return {
            "text": "The air conditioner in ARC room 205 is noisy.",
            "valid_buildings": ["ARC"],
            "valid_priorities": ["NORMAL"],
        }

    def fake_ollama(self, reviewer_status: str):
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.91})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "NORMAL",
                        "summary": "Air conditioner in ARC room 205 is noisy.",
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps(
                    {
                        "draft_wo_description": "Check ARC room 205 air conditioner.",
                        "internal_note": "Advisory draft only.",
                        "client_reply": "Thanks, we captured the request.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                if reviewer_status == "raise_if_called":
                    raise AssertionError("reviewer should not run")
                return json.dumps(
                    {
                        "status": reviewer_status,
                        "human_review_recommended": reviewer_status == "warning",
                        "risk_flags": ["review draft"] if reviewer_status == "warning" else [],
                        "notes": ["Client reply may be too terse."] if reviewer_status == "warning" else [],
                    }
                )
            raise AssertionError(system)

        return fake_call_ollama


if __name__ == "__main__":
    unittest.main()
