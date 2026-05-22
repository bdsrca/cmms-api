"""Callback wiring shared by saved test and prompt comparison routes."""

from collections.abc import Awaitable, Callable
from typing import Any

from .config import SUPPORTED_PROMPT_ENDPOINTS
from .prompts import prompt_row_for
from .test_cases import run_test_case_row

EndpointRunner = Callable[..., Awaitable[dict[str, Any]]]
RunnerKwargsCallback = Callable[[], dict[str, Any]]
PromptComparisonRunner = Callable[..., Awaitable[dict[str, Any]]]


def build_test_runner_callbacks(
    endpoint_runner: EndpointRunner,
) -> tuple[RunnerKwargsCallback, RunnerKwargsCallback, PromptComparisonRunner]:
    def test_case_runner_kwargs() -> dict[str, Any]:
        return {
            "endpoint_runner": endpoint_runner,
            "prompt_row_for": prompt_row_for,
            "supported_prompt_endpoints": SUPPORTED_PROMPT_ENDPOINTS,
        }

    def test_suite_runner_kwargs() -> dict[str, Any]:
        return {
            "run_test_case_row": run_test_case_row,
            "prompt_row_for": prompt_row_for,
            "supported_prompt_endpoints": SUPPORTED_PROMPT_ENDPOINTS,
            "test_case_runner_kwargs": test_case_runner_kwargs(),
        }

    async def run_test_case_row_for_prompt_comparison(
        row: Any,
        prompt_id: int | None = None,
        environment_override: str | None = None,
    ) -> dict[str, Any]:
        return await run_test_case_row(
            row,
            prompt_id=prompt_id,
            environment_override=environment_override,
            **test_case_runner_kwargs(),
        )

    return test_case_runner_kwargs, test_suite_runner_kwargs, run_test_case_row_for_prompt_comparison
