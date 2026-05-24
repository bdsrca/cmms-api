import json
import unittest
from unittest.mock import patch

from app.ai_endpoints import execute_ai_endpoint_for_test
from app.test_cases import run_test_case_row


class SafetyReviewerPromptOverrideTests(unittest.IsolatedAsyncioTestCase):
    async def test_test_case_runner_passes_reviewer_prompt_id_to_endpoint_runner(self) -> None:
        calls = []

        async def endpoint_runner(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return {
                "run_id": "run_test",
                "review": {"status": "pass", "human_review_recommended": False, "risk_flags": []},
            }

        def prompt_row_for(endpoint, prompt_id):
            return {"id": prompt_id, "version": "draft-reviewer"}

        row = {
            "id": 101,
            "endpoint": "cmms-intake",
            "environment_code": "DEFAULT",
            "input_text": "The air conditioner in ARC room 205 is noisy.",
            "expected_json": json.dumps({"review_status": "pass"}),
        }

        await run_test_case_row(
            row,
            reviewer_prompt_id=77,
            endpoint_runner=endpoint_runner,
            prompt_row_for=prompt_row_for,
            supported_prompt_endpoints={"cmms-intake"},
        )

        self.assertEqual(calls[0]["kwargs"]["reviewer_prompt_id"], 77)

    async def test_execute_ai_endpoint_for_test_uses_reviewer_prompt_override(self) -> None:
        reviewer_models = []
        reviewer_prompt_ids = []

        async def fake_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            system = messages[0]["content"]
            if "Classify the CMMS request type only" in system:
                return json.dumps({"request_type": "HVAC", "confidence": 0.9})
            if "Extract CMMS intake fields" in system:
                return json.dumps(
                    {
                        "building": "ARC",
                        "room": "205",
                        "priority": "NORMAL",
                        "summary": "AC in ARC room 205 is noisy.",
                    }
                )
            if "Generate advisory" in system:
                return json.dumps(
                    {
                        "draft_wo_description": "AC in ARC room 205 is noisy.",
                        "internal_note": "Review before CMMS workflow.",
                        "client_reply": "Thanks, we captured the request.",
                    }
                )
            if "Safety Reviewer Agent" in system:
                reviewer_models.append(model)
                return json.dumps({"status": "warning", "human_review_recommended": True, "risk_flags": ["Draft prompt tested"]})
            raise AssertionError(system[:120])

        def fake_reviewer_prompt_messages(endpoint, context, prompt_id=None):
            reviewer_prompt_ids.append(prompt_id)
            return (
                [{"role": "system", "content": "/no_think Safety Reviewer Agent"}, {"role": "user", "content": "{}"}],
                {"prompt_id": prompt_id, "prompt_version": "draft-reviewer", "model": "qwen3:8b", "temperature": 0.1},
            )

        with patch("app.safety_reviewer.prompt_messages", new=fake_reviewer_prompt_messages):
            data = await execute_ai_endpoint_for_test(
                "cmms-intake",
                "The air conditioner in ARC room 205 is making loud noise.",
                "DEFAULT",
                reviewer_prompt_id=77,
                call_ollama_func=fake_ollama,
                request_factory=lambda **kwargs: type("Payload", (), {**kwargs, "workflow_mode": "full"})(),
            )

        self.assertEqual(data["review"]["status"], "warning")
        self.assertIn("trace", data)
        self.assertEqual(reviewer_models, ["qwen3:8b"])
        self.assertEqual(reviewer_prompt_ids, [77])


if __name__ == "__main__":
    unittest.main()
