import json
import unittest

from app.config import DEFAULT_PROMPT_VERSIONS, SUPPORTED_PROMPT_ENDPOINTS
from app.models import IntakeResponse
from app.safety_reviewer import (
    failed_reviewer_block,
    normalize_reviewer_output,
    run_safety_reviewer_agent,
    skipped_reviewer_block,
)
from app.test_cases import compare_test_case_result


class SafetyReviewerTests(unittest.TestCase):
    def test_normalize_reviewer_output_keeps_advisory_shape(self) -> None:
        review = normalize_reviewer_output(
            {
                "status": "pass",
                "human_review_recommended": True,
                "risk_flags": [" Missing info ", "Missing info", ""],
                "notes": ["Review the client reply."],
            }
        )

        self.assertEqual(
            review,
            {
                "enabled": True,
                "status": "pass",
                "human_review_recommended": True,
                "risk_flags": ["Missing info"],
                "notes": ["Review the client reply."],
                "source": "safety_reviewer_agent",
            },
        )

    def test_unknown_status_and_bad_lists_are_normalized(self) -> None:
        review = normalize_reviewer_output(
            {
                "status": "needs-work",
                "human_review_recommended": "yes",
                "risk_flags": "not-a-list",
                "notes": "not-a-list",
            }
        )

        self.assertEqual(review["status"], "warning")
        self.assertFalse(review["human_review_recommended"])
        self.assertEqual(review["risk_flags"], [])
        self.assertEqual(review["notes"], [])

    def test_skipped_and_failed_blocks_are_stable(self) -> None:
        skipped = skipped_reviewer_block("Skipped because output contract validation failed.")
        failed = failed_reviewer_block("Safety reviewer returned invalid JSON")

        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(skipped["enabled"], False)
        self.assertEqual(failed["status"], "fail")
        self.assertEqual(failed["source"], "safety_reviewer_agent")
        self.assertFalse(failed["human_review_recommended"])


class SafetyReviewerPromptConfigTests(unittest.TestCase):
    def test_reviewer_prompt_endpoint_is_supported_and_seeded(self) -> None:
        self.assertIn("cmms-intake-reviewer", SUPPORTED_PROMPT_ENDPOINTS)
        prompt = DEFAULT_PROMPT_VERSIONS["cmms-intake-reviewer"]

        self.assertEqual(prompt["version"], "v1")
        self.assertIn("/no_think", prompt["system_prompt"])
        self.assertIn("Return JSON only", prompt["system_prompt"])
        self.assertIn("Do not change extracted fields", prompt["system_prompt"])
        self.assertEqual(prompt["user_template"], "{{context_json}}")


class SafetyReviewerCallTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_safety_reviewer_agent_normalizes_model_output(self) -> None:
        calls = []

        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            calls.append({"messages": messages, "temperature": temperature, "model": model})
            return json.dumps(
                {
                    "status": "warning",
                    "human_review_recommended": True,
                    "risk_flags": ["Unsafe promise"],
                    "notes": ["Client reply sounds too certain."],
                }
            )

        review, prompt_meta = await run_safety_reviewer_agent(
            result={"summary": "AC is noisy.", "building": "ARC"},
            contract={"valid": True, "errors": [], "warnings": [], "version": "v1"},
            ai_validation={"valid": True, "errors": [], "warnings": [], "normalized": {}},
            drafts={"client_reply": "We will dispatch someone now."},
            call_ollama_func=fake_call_ollama,
        )

        self.assertEqual(review["status"], "warning")
        self.assertTrue(review["human_review_recommended"])
        self.assertEqual(review["risk_flags"], ["Unsafe promise"])
        self.assertEqual(prompt_meta["endpoint"], "cmms-intake-reviewer")
        self.assertEqual(len(calls), 1)
        self.assertIn("AC is noisy.", calls[0]["messages"][1]["content"])

    async def test_run_safety_reviewer_agent_invalid_json_returns_failed_block(self) -> None:
        async def fake_call_ollama(messages, timeout=120, temperature=None, model="qwen3:8b"):
            return "not json"

        review, _prompt_meta = await run_safety_reviewer_agent(
            result={"summary": "AC is noisy."},
            contract={"valid": True, "errors": [], "warnings": [], "version": "v1"},
            ai_validation={"valid": True, "errors": [], "warnings": [], "normalized": {}},
            drafts={},
            call_ollama_func=fake_call_ollama,
        )

        self.assertEqual(review["status"], "fail")
        self.assertEqual(review["source"], "safety_reviewer_agent")


class SafetyReviewerResponseModelTests(unittest.TestCase):
    def test_intake_response_allows_review_block(self) -> None:
        response = IntakeResponse(
            model="qwen3:8b",
            review={
                "enabled": True,
                "status": "pass",
                "human_review_recommended": False,
                "risk_flags": [],
                "notes": [],
                "source": "safety_reviewer_agent",
            },
        )

        self.assertEqual(response.review["status"], "pass")


class SafetyReviewerTestCaseComparisonTests(unittest.TestCase):
    def test_comparison_supports_reviewer_assertions(self) -> None:
        comparison = compare_test_case_result(
            {
                "review_status": "warning",
                "review_human_review_recommended": True,
                "review_risk_flags_contains": ["Unsafe promise"],
            },
            {
                "review": {
                    "status": "warning",
                    "human_review_recommended": True,
                    "risk_flags": ["Unsafe promise", "Review draft"],
                }
            },
        )

        self.assertTrue(comparison["passed"])
        self.assertEqual(comparison["review_result"]["status"]["actual"], "warning")
        self.assertTrue(comparison["review_result"]["risk_flags_contains"]["passed"])


if __name__ == "__main__":
    unittest.main()
