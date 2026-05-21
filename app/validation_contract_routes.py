"""Validation rule and output contract route registration."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .output_contracts import (
    activate_output_contract as activate_output_contract_helper,
    create_output_contract as create_output_contract_helper,
    list_output_contracts as list_output_contracts_helper,
    list_output_contracts_for_endpoint as list_output_contracts_for_endpoint_helper,
    patch_output_contract as patch_output_contract_helper,
    read_output_contract as read_output_contract_helper,
    validate_contract_sample as validate_contract_sample_helper,
)
from .security import PortalUser, current_admin, current_user
from .validation_rules import (
    get_validation_rules,
    patch_validation_rule as patch_validation_rule_helper,
    reset_environment_validation_rules as reset_environment_validation_rules_helper,
    validate_sample as validate_sample_helper,
)


router = APIRouter()


class ValidationRulePatchRequest(BaseModel):
    enabled: bool | None = None
    required: bool | None = None
    code_category: str | None = None
    must_match_code_list: bool | None = None
    allow_unknown: bool | None = None
    severity: str | None = Field(default=None, pattern="^(error|warning)$")


class ValidateSampleRequest(BaseModel):
    values: dict[str, Any] | None = None


class OutputContractRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=80)
    version: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    schema_def: dict[str, Any] = Field(..., alias="schema_json")
    strict_mode: bool = True
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")


class OutputContractPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    schema_def: dict[str, Any] | None = Field(default=None, alias="schema_json")
    strict_mode: bool | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|archived)$")


@router.get("/api/environments/{environment_code}/validation-rules")
async def list_validation_rules(environment_code: str, user: PortalUser = Depends(current_user)) -> list[dict[str, Any]]:
    return get_validation_rules(environment_code.upper())


@router.patch("/api/admin/environments/{environment_code}/validation-rules/{rule_id}")
async def patch_validation_rule(
    environment_code: str,
    rule_id: int,
    payload: ValidationRulePatchRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    return patch_validation_rule_helper(environment_code, rule_id, payload)


@router.post("/api/admin/environments/{environment_code}/validation-rules/reset-defaults")
async def reset_environment_validation_rules(environment_code: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return reset_environment_validation_rules_helper(environment_code)


@router.post("/api/environments/{environment_code}/validate-sample")
async def validate_sample(environment_code: str, payload: ValidateSampleRequest, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return validate_sample_helper(environment_code, payload.values)


@router.get("/api/output-contracts/{endpoint}")
async def read_output_contract(endpoint: str, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return read_output_contract_helper(endpoint)


@router.get("/api/admin/output-contracts")
async def list_output_contracts(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_output_contracts_helper()


@router.get("/api/admin/output-contracts/{endpoint}")
async def list_output_contracts_for_endpoint(endpoint: str, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_output_contracts_for_endpoint_helper(endpoint)


@router.post("/api/admin/output-contracts")
async def create_output_contract(payload: OutputContractRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return create_output_contract_helper(payload, user)


@router.patch("/api/admin/output-contracts/{contract_id}")
async def patch_output_contract(contract_id: int, payload: OutputContractPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return patch_output_contract_helper(contract_id, payload, user)


@router.post("/api/admin/output-contracts/{contract_id}/activate")
async def activate_output_contract(contract_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return activate_output_contract_helper(contract_id, user)


@router.post("/api/admin/output-contracts/{contract_id}/validate-sample")
async def validate_contract_sample(contract_id: int, payload: ValidateSampleRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return validate_contract_sample_helper(contract_id, payload.values)
