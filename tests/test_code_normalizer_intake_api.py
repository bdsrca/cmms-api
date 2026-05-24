import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as app_main
from app.security import PortalUser, current_user


class CodeNormalizerIntakeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = "code-normalizer-test-key"

    def payload(self) -> dict:
        return {
            "text": "The leak in ARC room 205 is urgent.",
            "environment_code": "DEFAULT",
            "workflow_mode": "full",
        }

    def fake_ollama(self, normalizer_priority: str = "URGENT", confidence: float = 0.91):
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"] if messages else ""
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "Plumbing", "confidence": 0.9})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "urgent phrase",
                        "summary": "Water leak in ARC room 205.",
                    }
                )
            if "Code Normalization Suggestion Agent" in system:
                return json.dumps(
                    {
                        "suggestions": [
                            {
                                "field": "priority",
                                "input_value": "urgent phrase",
                                "suggested_code": normalizer_priority,
                                "confidence": confidence,
                                "reason": "Urgent wording.",
                            }
                        ]
                    }
                )
            if "Generate advisory CMMS draft text only" in system:
                return json.dumps(
                    {
                        "draft_wo_description": "Water leak in ARC room 205. Priority URGENT.",
                        "internal_note": "Validated intake. Ready for human review or controlled CMMS workflow.",
                        "client_reply": "Thanks, we captured the urgent leak request for ARC room 205.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                return json.dumps({"status": "pass", "human_review_recommended": False, "risk_flags": [], "notes": []})
            raise AssertionError(system)

        return fake_call_ollama

    def test_invalid_priority_is_normalized_before_environment_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["code_normalization"]["status"], "applied")
        self.assertEqual(data["code_normalization"]["applied"], {"priority": "URGENT"})
        self.assertEqual(data["result"]["priority"], "URGENT")
        self.assertEqual(data["ai_validation"]["normalized"].get("priority"), "URGENT")
        self.assertEqual(data["review"]["status"], "pass")

    def test_low_confidence_suggestion_is_rejected(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama(confidence=0.2)

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )

        data = response.json()
        self.assertEqual(data["code_normalization"]["status"], "rejected")
        self.assertEqual(data["code_normalization"]["rejected"][0]["reason_code"], "confidence_below_threshold")

    def test_contract_failure_skips_normalizer(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()
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
                    headers={"x-api-key": "code-normalizer-test-key"},
                    json=self.payload(),
                )

        data = response.json()
        self.assertEqual(data["code_normalization"]["status"], "skipped")
        self.assertEqual(data["ai_validation"]["status"], "not_run")

    def test_response_model_exposes_code_normalization(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()

        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/ai/cmms-intake",
                headers={"x-api-key": "code-normalizer-test-key"},
                json=self.payload(),
            )

        self.assertIn("code_normalization", response.json())

    def test_workflow_trace_records_code_normalizer_step_before_environment_validation(self) -> None:
        app_main.ai_call_ollama = self.fake_ollama()
        app_main.app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="admin", role="admin")
        try:
            with TestClient(app_main.app) as client:
                response = client.post(
                    "/api/ai/cmms-intake",
                    headers={"x-api-key": "code-normalizer-test-key"},
                    json=self.payload(),
                )
                trace = client.get(f"/api/admin/workflow-runs/{response.json()['run_id']}")
        finally:
            app_main.app.dependency_overrides.pop(current_user, None)

        self.assertEqual(trace.status_code, 200, trace.text)
        steps = trace.json()["steps"]
        names = [step["step_name"] for step in steps]

        self.assertIn("code_normalization_suggestion_agent", names)
        self.assertLess(names.index("output_contract_validation"), names.index("code_normalization_suggestion_agent"))
        self.assertLess(names.index("code_normalization_suggestion_agent"), names.index("environment_validation"))
        self.assertLess(names.index("environment_validation"), names.index("draft_generation"))


if __name__ == "__main__":
    unittest.main()
