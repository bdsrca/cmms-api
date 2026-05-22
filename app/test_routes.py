"""Saved test case, suite, and replay route registration."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .security import PortalUser, current_admin
from .test_cases import (
    create_test_case as create_test_case_helper,
    create_test_case_from_workflow_run as create_test_case_from_workflow_run_helper,
    delete_test_case as delete_test_case_helper,
    get_test_case as get_test_case_helper,
    get_test_case_run as get_test_case_run_helper,
    list_test_case_runs as list_test_case_runs_helper,
    list_test_cases as list_test_cases_helper,
    patch_test_case as patch_test_case_helper,
    replay_workflow_run as replay_workflow_run_helper,
    run_test_case as run_test_case_helper,
    run_test_case_batch as run_test_case_batch_helper,
)
from .test_suites import (
    add_test_suite_case as add_test_suite_case_helper,
    create_test_suite as create_test_suite_helper,
    delete_test_suite as delete_test_suite_helper,
    get_test_suite as get_test_suite_helper,
    get_test_suite_run as get_test_suite_run_helper,
    list_test_suite_runs as list_test_suite_runs_helper,
    list_test_suites as list_test_suites_helper,
    patch_test_suite as patch_test_suite_helper,
    remove_test_suite_case as remove_test_suite_case_helper,
    run_test_suite as run_test_suite_helper,
    run_test_suite_batch as run_test_suite_batch_helper,
)


class TestCaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    endpoint: str = Field(..., min_length=1, max_length=80)
    environment_code: str | None = None
    input_text: str = Field(..., min_length=1, max_length=4000)
    source: str = "manual"
    expected_json: dict[str, Any] | None = None
    enabled: bool = True
    tags: str | None = None
    notes: str | None = None


class TestCasePatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    endpoint: str | None = Field(default=None, min_length=1, max_length=80)
    environment_code: str | None = None
    input_text: str | None = Field(default=None, min_length=1, max_length=4000)
    source: str | None = None
    expected_json: dict[str, Any] | None = None
    enabled: bool | None = None
    tags: str | None = None
    notes: str | None = None


class TestCaseRunRequest(BaseModel):
    environment_code: str | None = None
    prompt_id: int | None = None


class TestCaseBatchRunRequest(BaseModel):
    endpoint: str | None = None
    environment_code: str | None = None
    enabled_only: bool = True
    prompt_id: int | None = None


class TestSuiteRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    endpoint: str = Field(..., min_length=1, max_length=80)
    environment_code: str | None = None
    description: str | None = None
    enabled: bool = True
    required_for_promotion: bool = False
    min_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    zero_regression_required: bool = True
    zero_error_required: bool = True
    tags: str | None = None


class TestSuitePatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    endpoint: str | None = Field(default=None, min_length=1, max_length=80)
    environment_code: str | None = None
    description: str | None = None
    enabled: bool | None = None
    required_for_promotion: bool | None = None
    min_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    zero_regression_required: bool | None = None
    zero_error_required: bool | None = None
    tags: str | None = None


class TestSuiteCaseRequest(BaseModel):
    test_case_id: int
    sort_order: int = 0
    enabled: bool = True


class TestSuiteRunRequest(BaseModel):
    prompt_id: int | None = None
    environment_code: str | None = None


class TestSuiteBatchRunRequest(BaseModel):
    endpoint: str | None = None
    environment_code: str | None = None
    prompt_id: int | None = None
    required_only: bool = False
    enabled_only: bool = True


class WorkflowRunCreateTestCaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    expected_json: dict[str, Any] | None = None
    tags: str | None = None
    notes: str | None = None


def build_test_router(
    *,
    test_case_runner_kwargs: Callable[[], dict[str, Any]],
    test_suite_runner_kwargs: Callable[[], dict[str, Any]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/test-cases")
    async def list_test_cases(
        endpoint: str | None = None,
        environment_code: str | None = None,
        enabled: bool | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> list[dict[str, Any]]:
        return list_test_cases_helper(endpoint=endpoint, environment_code=environment_code, enabled=enabled)

    @router.post("/api/admin/test-cases")
    async def create_test_case(payload: TestCaseRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return create_test_case_helper(payload, user)

    @router.get("/api/admin/test-cases/{test_case_id}")
    async def get_test_case(test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        item = get_test_case_helper(test_case_id)
        if not item:
            raise HTTPException(status_code=404, detail="Test case not found")
        return item

    @router.patch("/api/admin/test-cases/{test_case_id}")
    async def patch_test_case(
        test_case_id: int,
        payload: TestCasePatchRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return patch_test_case_helper(test_case_id, payload, user)

    @router.delete("/api/admin/test-cases/{test_case_id}")
    async def delete_test_case(test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return delete_test_case_helper(test_case_id)

    @router.post("/api/admin/test-cases/{test_case_id}/run")
    async def run_test_case(
        test_case_id: int,
        payload: TestCaseRunRequest | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await run_test_case_helper(test_case_id, payload, **test_case_runner_kwargs())

    @router.post("/api/admin/test-cases/run-batch")
    async def run_test_case_batch(
        payload: TestCaseBatchRunRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await run_test_case_batch_helper(payload, **test_case_runner_kwargs())

    @router.get("/api/admin/test-case-runs")
    async def list_test_case_runs(
        status: str | None = None,
        limit: int = 50,
        user: PortalUser = Depends(current_admin),
    ) -> list[dict[str, Any]]:
        return list_test_case_runs_helper(status=status, limit=limit)

    @router.get("/api/admin/test-case-runs/{run_id}")
    async def get_test_case_run(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        item = get_test_case_run_helper(run_id)
        if not item:
            raise HTTPException(status_code=404, detail="Test case run not found")
        return item

    @router.get("/api/admin/test-suites")
    async def list_test_suites(
        endpoint: str | None = None,
        environment_code: str | None = None,
        enabled: bool | None = None,
        required_for_promotion: bool | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> list[dict[str, Any]]:
        return list_test_suites_helper(
            endpoint=endpoint,
            environment_code=environment_code,
            enabled=enabled,
            required_for_promotion=required_for_promotion,
        )

    @router.post("/api/admin/test-suites")
    async def create_test_suite(payload: TestSuiteRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return create_test_suite_helper(payload, user)

    @router.post("/api/admin/test-suites/run-batch")
    async def run_test_suite_batch(
        payload: TestSuiteBatchRunRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await run_test_suite_batch_helper(payload, user, **test_suite_runner_kwargs())

    @router.get("/api/admin/test-suite-runs")
    async def list_test_suite_runs(
        status: str | None = None,
        limit: int = 50,
        user: PortalUser = Depends(current_admin),
    ) -> list[dict[str, Any]]:
        return list_test_suite_runs_helper(status=status, limit=limit)

    @router.get("/api/admin/test-suite-runs/{suite_run_id}")
    async def get_test_suite_run(suite_run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        item = get_test_suite_run_helper(suite_run_id)
        if not item:
            raise HTTPException(status_code=404, detail="Test suite run not found")
        return item

    @router.get("/api/admin/test-suites/{suite_id}")
    async def get_test_suite(suite_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return get_test_suite_helper(suite_id)

    @router.patch("/api/admin/test-suites/{suite_id}")
    async def patch_test_suite(
        suite_id: str,
        payload: TestSuitePatchRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return patch_test_suite_helper(suite_id, payload, user)

    @router.delete("/api/admin/test-suites/{suite_id}")
    async def delete_test_suite(suite_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return delete_test_suite_helper(suite_id)

    @router.post("/api/admin/test-suites/{suite_id}/cases")
    async def add_test_suite_case(
        suite_id: str,
        payload: TestSuiteCaseRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return add_test_suite_case_helper(suite_id, payload)

    @router.delete("/api/admin/test-suites/{suite_id}/cases/{test_case_id}")
    async def remove_test_suite_case(
        suite_id: str,
        test_case_id: int,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return remove_test_suite_case_helper(suite_id, test_case_id)

    @router.post("/api/admin/test-suites/{suite_id}/run")
    async def run_test_suite(
        suite_id: str,
        payload: TestSuiteRunRequest | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await run_test_suite_helper(suite_id, payload, user, **test_suite_runner_kwargs())

    @router.post("/api/admin/workflow-runs/{run_id}/create-test-case")
    async def create_test_case_from_workflow_run(
        run_id: str,
        payload: WorkflowRunCreateTestCaseRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await create_test_case_from_workflow_run_helper(run_id, payload, user)

    @router.post("/api/admin/workflow-runs/{run_id}/replay")
    async def replay_workflow_run(
        run_id: str,
        payload: TestCaseRunRequest | None = None,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return await replay_workflow_run_helper(run_id, payload, **test_case_runner_kwargs())

    return router
