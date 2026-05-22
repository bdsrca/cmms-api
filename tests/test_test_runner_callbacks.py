import unittest
from unittest.mock import AsyncMock, patch

from app import config, prompts
from app.test_runner_callbacks import build_test_runner_callbacks


class TestRunnerCallbacksTests(unittest.IsolatedAsyncioTestCase):
    async def test_callbacks_share_endpoint_runner_and_prompt_wiring(self) -> None:
        async def endpoint_runner(*args, **kwargs):
            return {"args": args, "kwargs": kwargs}

        test_case_runner_kwargs, test_suite_runner_kwargs, comparison_runner = build_test_runner_callbacks(
            endpoint_runner
        )

        case_kwargs = test_case_runner_kwargs()
        suite_kwargs = test_suite_runner_kwargs()

        self.assertIs(case_kwargs["endpoint_runner"], endpoint_runner)
        self.assertIs(case_kwargs["prompt_row_for"], prompts.prompt_row_for)
        self.assertIs(case_kwargs["supported_prompt_endpoints"], config.SUPPORTED_PROMPT_ENDPOINTS)
        self.assertIs(suite_kwargs["test_case_runner_kwargs"]["endpoint_runner"], endpoint_runner)

        with patch(
            "app.test_runner_callbacks.run_test_case_row",
            new=AsyncMock(return_value={"status": "passed"}),
        ) as run_test_case_row:
            result = await comparison_runner(
                {"id": 7},
                prompt_id=12,
                environment_override="DEFAULT",
            )

        self.assertEqual(result, {"status": "passed"})
        run_test_case_row.assert_awaited_once()
        args, kwargs = run_test_case_row.await_args
        self.assertEqual(args[0], {"id": 7})
        self.assertEqual(kwargs["prompt_id"], 12)
        self.assertEqual(kwargs["environment_override"], "DEFAULT")
        self.assertIs(kwargs["endpoint_runner"], endpoint_runner)


if __name__ == "__main__":
    unittest.main()
