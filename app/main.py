from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sqlite3
import subprocess
import threading
import time
from typing import Any

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .ai_endpoints import (
    call_ollama as ai_call_ollama,
    cmms_assistant as cmms_assistant_helper,
    cmms_intake as cmms_intake_helper,
    execute_ai_endpoint_for_test as execute_ai_endpoint_for_test_helper,
    extract_work_order_fields as extract_work_order_fields_helper,
    summarize_work_order as summarize_work_order_helper,
)
from .api_keys import (
    create_api_key as create_api_key_helper,
    list_api_keys as list_api_keys_helper,
    migrate_json_api_keys,
    patch_api_key as patch_api_key_helper,
    require_api_key,
)
from .auth_routes import router as auth_router
from .core_routes import router as core_router
from .db import (
    BASE_DIR,
    DATA_DIR,
    LOG_DIR,
    LOG_FILE,
    db_execute,
    db_fetchall,
    db_fetchone,
    init_db as init_database,
)
from .email_intake import build_email_intake_text
from .environments import (
    get_environment_values,
    seed_default_environment,
)
from .environment_routes import router as environment_router
from .security import (
    AuthContext,
    PortalUser,
    bootstrap_admin_user,
    current_admin,
    current_user,
    hash_password,
)
from .output_contracts import (
    active_contract,
    seed_default_output_contracts,
)
from .prompt_comparisons import (
    get_prompt_comparison as get_prompt_comparison_helper,
    list_prompt_comparisons as list_prompt_comparisons_helper,
    run_prompt_comparison as run_prompt_comparison_helper,
)
from .prompts import (
    activate_prompt_version as activate_prompt_version_helper,
    active_prompt_info,
    archive_prompt_version as archive_prompt_version_helper,
    create_prompt_version as create_prompt_version_helper,
    list_prompt_versions as list_prompt_versions_helper,
    list_prompt_versions_for_endpoint as list_prompt_versions_for_endpoint_helper,
    patch_prompt_version as patch_prompt_version_helper,
    prompt_row_for,
    prompt_version_by_id,
    seed_default_prompt_versions,
    test_prompt_version as test_prompt_version_helper,
)
from .prompt_promotions import (
    check_prompt_promotion_gate,
    get_prompt_promotion as get_prompt_promotion_helper,
    list_prompt_promotions as list_prompt_promotions_helper,
)
from .regression_dashboard import build_regression_dashboard
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
    run_test_case_row as run_test_case_row_helper,
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
from .validation_rules import (
    validate_ai_output,
)
from .validation_contract_routes import router as validation_contract_router
from .workflow_trace import (
    cleanup_workflow_runs,
    get_workflow_run,
    list_workflow_runs,
)


MODEL_NAME = "qwen3:8b"
SERVICE_NAME = "local-cmms-llm-api"

ALLOWED_REQUEST_TYPES = {
    "HVAC",
    "Plumbing",
    "Electrical",
    "Cleaning",
    "Security",
    "Key Request",
    "Rekey Request",
    "IT",
    "General Maintenance",
    "Unknown",
}

CODE_CATEGORIES = {
    "buildings": "Buildings",
    "rooms": "Rooms",
    "priorities": "Priorities",
    "work_order_types": "Work order types",
    "assign_to": "Assign to",
    "issue_to_employee_number": "Issue to employee #",
    "job_type": "Job type",
}

DEFAULT_VALIDATION_RULES = [
    ("building", "Building", True, "buildings", True, False, "error", 10),
    ("room", "Room", False, "rooms", True, False, "warning", 20),
    ("priority", "Priority", False, "priorities", True, False, "warning", 30),
    ("work_order_type", "Work Order Type", False, "work_order_types", True, False, "warning", 40),
    ("assign_to", "Assign To", False, "assign_to", True, False, "warning", 50),
    ("issue_to", "Issue To", False, "issue_to", True, False, "warning", 60),
    ("job_type", "Job Type", False, "job_type", True, False, "warning", 70),
]

DEFAULT_CMMS_INTAKE_CONTRACT = {
    "type": "object",
    "required": ["summary"],
    "properties": {
        "summary": {"type": "string"},
        "building": {"type": ["string", "null"]},
        "room": {"type": ["string", "null"]},
        "priority": {"type": ["string", "null"]},
        "work_order_type": {"type": ["string", "null"]},
        "assign_to": {"type": ["string", "null"]},
        "issue_to": {"type": ["string", "null"]},
        "job_type": {"type": ["string", "null"]},
        "confidence": {"type": ["number", "null"]},
    },
    "additionalProperties": False,
}

SUPPORTED_PROMPT_ENDPOINTS = {
    "cmms-intake",
    "summarize-work-order",
    "extract-work-order-fields",
    "cmms-assistant",
}

DEFAULT_PROMPT_VERSIONS = {
    "summarize-work-order": {
        "version": "v1",
        "name": "Default summarize prompt",
        "temperature": 0.1,
        "system_prompt": (
            "/no_think\n"
            "You summarize CMMS work order requests. Return only a concise plain-text "
            "summary in one clear sentence. Do not invent missing facts."
        ),
        "user_template": "{{text}}",
    },
    "cmms-assistant": {
        "version": "v1",
        "name": "Default controlled assistant prompt",
        "temperature": 0.2,
        "system_prompt": (
            "/no_think\n"
            "You are a controlled CMMS LLM portal assistant for local testing. "
            "Answer conversationally and concisely, but stay within CMMS intake, API usage, "
            "validation, troubleshooting, and drafting help. The user may write in English, "
            "Chinese, French, Spanish, Japanese, Korean, or mixed language. "
            "Do not claim that a work order was created. Do not approve requests, send emails, "
            "write to CMMS, expose secrets, or provide instructions to bypass authentication. "
            "If the user asks for an action outside advisory mode, explain the safety boundary."
        ),
        "user_template": "{{text}}",
    },
    "extract-work-order-fields": {
        "version": "v1",
        "name": "Default field extraction prompt",
        "temperature": 0.1,
        "system_prompt": (
            "/no_think\n"
            "Extract CMMS fields from the request. Return JSON only with this shape: "
            "{\"request_type\":\"HVAC\",\"building\":\"ARC\",\"room\":\"205\",\"priority\":\"NORMAL\","
            "\"summary\":\"Air conditioner in ARC room 205 is making loud noise.\","
            "\"missing_fields\":[],\"needs_human_review\":false,\"confidence\":0.85}. "
            "Allowed request_type values: {{allowed_request_types}}. "
            "Valid buildings: {{valid_buildings}}. Valid priorities: {{valid_priorities}}. "
            "The user request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
            "Extract CMMS fields from the request. Return final structured field values using configured CMMS codes when possible. "
            "Do not return translated free-text values for code fields if a configured code should be used. "
            "Use null for unknown building or room. Do not invent missing facts."
        ),
        "user_template": "{{text}}",
    },
    "cmms-intake": {
        "version": "v1",
        "name": "Default intake workflow prompts",
        "temperature": 0.1,
        "system_prompt": json.dumps(
            {
                "classifier": (
                    "/no_think\n"
                    "Classify the CMMS request type only. Return JSON only with this shape: "
                    "{\"request_type\":\"HVAC\",\"confidence\":0.85}. "
                    "Allowed request_type values: {{allowed_request_types}}. "
                    "The request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
                    "Use Unknown when unclear."
                ),
                "field_extractor": (
                    "/no_think\n"
                    "Extract CMMS intake fields. Return JSON only with this shape: "
                    "{\"building\":\"ARC\",\"room\":\"205\",\"priority\":\"NORMAL\","
                    "\"summary\":\"Air conditioner in ARC room 205 is making loud noise.\"}. "
                    "Valid buildings: {{valid_buildings}}. Valid priorities: {{valid_priorities}}. "
                    "The user request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
                    "Extract CMMS fields from the request. Return final structured field values using configured CMMS codes when possible. "
                    "Do not return translated free-text values for code fields if a configured code should be used. "
                    "Use null for unknown building or room. Do not invent missing facts."
                ),
                "draft_generator": (
                    "/no_think\n"
                    "Generate advisory CMMS draft text only. Return JSON only with this shape: "
                    "{\"draft_wo_description\":\"string\",\"internal_note\":\"string\",\"client_reply\":\"string\"}. "
                    "Do not claim a work order was created. Do not promise approval, dispatch, or email."
                ),
            },
            ensure_ascii=True,
            indent=2,
        ),
        "user_template": "{{text}}",
    },
}

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(SERVICE_NAME)

app = FastAPI(title="Local CMMS LLM API", version="1.0.0")
app.include_router(core_router)
app.include_router(auth_router)
app.include_router(environment_router)
app.include_router(validation_contract_router)


class SubmissionMetadata(BaseModel):
    submitted_by: str | None = Field(default=None, max_length=160)
    submitted_email: str | None = Field(default=None, max_length=320)
    submitted_phone: str | None = Field(default=None, max_length=80)
    submitted_at: str | None = Field(default=None, max_length=40)
    submitted_method: str | None = Field(default=None, max_length=40)


class IntakeLocation(BaseModel):
    building: str | None = Field(default=None, max_length=80)
    room: str | None = Field(default=None, max_length=80)
    area: str | None = Field(default=None, max_length=160)
    raw: str | None = Field(default=None, max_length=240)


class IntakeRequestMetadata(BaseModel):
    requested_due_at: str | None = Field(default=None, max_length=40)
    location: IntakeLocation | None = None


class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None
    source: str | None = None
    submission: SubmissionMetadata | None = None
    request: IntakeRequestMetadata | None = None


class SummaryResponse(BaseModel):
    summary: str


class AssistantResponse(BaseModel):
    mode: str
    response: str
    model: str
    safety: dict[str, Any]


class ExtractFieldsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None
    valid_buildings: list[str] | None = None
    valid_priorities: list[str] | None = None
    source: str | None = None
    submission: SubmissionMetadata | None = None
    request: IntakeRequestMetadata | None = None


class EmailIntakeRequest(BaseModel):
    from_email: str = Field(..., min_length=1, max_length=320)
    to_email: str = Field(..., min_length=1, max_length=320)
    subject: str = Field(..., min_length=1, max_length=240)
    body: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None
    submitted_by: str | None = Field(default=None, max_length=160)
    submitted_phone: str | None = Field(default=None, max_length=80)
    submitted_at: str | None = Field(default=None, max_length=40)
    requested_due_at: str | None = Field(default=None, max_length=40)
    location: IntakeLocation | None = None


class ExtractFieldsResponse(BaseModel):
    request_type: str
    building: str | None
    room: str | None
    priority: str
    summary: str
    missing_fields: list[str]
    needs_human_review: bool
    confidence: float


class IntakeFields(BaseModel):
    building: str | None
    room: str | None
    priority: str
    summary: str


class IntakeValidation(BaseModel):
    can_create_work_order: bool
    needs_human_review: bool
    missing_fields: list[str]
    errors: list[str]
    warnings: list[str]


class IntakeDrafts(BaseModel):
    draft_wo_description: str
    internal_note: str
    client_reply: str


class IntakeResponse(BaseModel):
    run_id: str | None = None
    endpoint: str | None = None
    environment_code: str | None = None
    trace: dict[str, Any] | None = None
    contract: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    ai_validation: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    request_type: str | None = None
    classification_confidence: float | None = None
    fields: IntakeFields | None = None
    validation: IntakeValidation | None = None
    drafts: IntakeDrafts | None = None
    model: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    owner: str | None = None


class ApiKeyPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None


class PromptVersionRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=80)
    version: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    system_prompt: str = Field(..., min_length=1)
    user_template: str = Field(default="{{text}}", min_length=1)
    model: str = Field(default=MODEL_NAME, min_length=1, max_length=80)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")


class PromptVersionPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_prompt: str | None = Field(default=None, min_length=1)
    user_template: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1, max_length=80)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class PromptTestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None


class PromotionCheckRequest(BaseModel):
    comparison_id: str | None = None


class PromptActivationRequest(BaseModel):
    comparison_id: str | None = None
    override: bool = False
    override_reason: str | None = None


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


class PromptComparisonRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=80)
    environment_code: str | None = None
    baseline_prompt_id: int
    candidate_prompt_id: int
    enabled_only: bool = True


class WorkflowRunCreateTestCaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    expected_json: dict[str, Any] | None = None
    tags: str | None = None
    notes: str | None = None


class SettingPatchRequest(BaseModel):
    value: str


class SystemStatusResponse(BaseModel):
    service: str
    model: str
    api_running: bool
    ollama_running: bool
    log_file: str


class LogResponse(BaseModel):
    log_file: str
    lines: list[str]


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_ms() -> int:
    return int(time.time() * 1000)


def require_local_control(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="System controls are local-only")


async def call_ollama(
    messages: list[dict[str, str]],
    timeout: int = 120,
    temperature: float | None = None,
    model: str = MODEL_NAME,
) -> str:
    return await ai_call_ollama(messages, timeout=timeout, temperature=temperature, model=model)


async def is_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True


async def wait_for_ollama(timeout_seconds: int = 15) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if await is_ollama_running():
            return True
        await asyncio.sleep(1)
    return False


def start_ollama_process() -> None:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="ollama.exe was not found on PATH") from exc


def stop_ollama_process() -> None:
    result = subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], capture_output=True, text=True, check=False)
    if result.returncode not in {0, 128}:
        detail = (result.stderr or result.stdout or "Could not stop Ollama").strip()
        raise HTTPException(status_code=500, detail=detail)


def read_log_lines(line_count: int) -> list[str]:
    safe_count = max(1, min(line_count, 1000))
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as log_file:
        return [line.rstrip("\r\n") for line in log_file.readlines()[-safe_count:]]


def shutdown_process_later() -> None:
    def delayed_exit() -> None:
        time.sleep(0.5)
        logger.info("service_forced_shutdown requested_by=ui")
        os._exit(0)

    threading.Thread(target=delayed_exit, daemon=True).start()


def summarize_prompt(text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "You summarize CMMS work order requests. Return only a concise plain-text "
                "summary in one clear sentence. Do not invent missing facts."
            ),
        },
        {"role": "user", "content": text},
    ]


def assistant_prompt(text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "You are a controlled CMMS LLM portal assistant for local testing. "
                "Answer conversationally and concisely, but stay within CMMS intake, API usage, "
                "validation, troubleshooting, and drafting help. The user may write in English, "
                "Chinese, French, Spanish, Japanese, Korean, or mixed language. "
                "Do not claim that a work order was created. Do not approve requests, send emails, "
                "write to CMMS, expose secrets, or provide instructions to bypass authentication. "
                "If the user asks for an action outside advisory mode, explain the safety boundary."
            ),
        },
        {"role": "user", "content": text},
    ]


def extract_prompt(text: str, valid_buildings: list[str], valid_priorities: list[str]) -> list[dict[str, str]]:
    multilingual_instruction = (
        "The user request may be in English, Chinese, French, Spanish, Japanese, Korean, "
        "or mixed language. Extract CMMS fields from the request. Return final structured "
        "field values using configured CMMS codes when possible. Do not return translated "
        "free-text values for code fields if a configured code should be used."
    )
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "Extract CMMS fields from the request. Return JSON only with this shape: "
                '{"request_type":"HVAC","building":"ARC","room":"205","priority":"NORMAL",'
                '"summary":"Air conditioner in ARC room 205 is making loud noise.",'
                '"missing_fields":[],"needs_human_review":false,"confidence":0.85}. '
                f"Allowed request_type values: {sorted(ALLOWED_REQUEST_TYPES)}. "
                f"Valid buildings: {valid_buildings}. Valid priorities: {valid_priorities}. "
                f"{multilingual_instruction} "
                "Use null for unknown building or room. Do not invent missing facts."
            ),
        },
        {"role": "user", "content": text},
    ]


def classifier_prompt(text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "Classify the CMMS request type only. Return JSON only with this shape: "
                '{"request_type":"HVAC","confidence":0.85}. '
                f"Allowed request_type values: {sorted(ALLOWED_REQUEST_TYPES)}. "
                "The request may be in English, Chinese, French, Spanish, Japanese, Korean, or mixed language. "
                "Use Unknown when unclear."
            ),
        },
        {"role": "user", "content": text},
    ]


def field_extractor_prompt(text: str, valid_buildings: list[str], valid_priorities: list[str]) -> list[dict[str, str]]:
    multilingual_instruction = (
        "The user request may be in English, Chinese, French, Spanish, Japanese, Korean, "
        "or mixed language. Extract CMMS fields from the request. Return final structured "
        "field values using configured CMMS codes when possible. Do not return translated "
        "free-text values for code fields if a configured code should be used."
    )
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "Extract CMMS intake fields. Return JSON only with this shape: "
                '{"building":"ARC","room":"205","priority":"NORMAL",'
                '"summary":"Air conditioner in ARC room 205 is making loud noise."}. '
                f"Valid buildings: {valid_buildings}. Valid priorities: {valid_priorities}. "
                f"{multilingual_instruction} "
                "Use null for unknown building or room. Do not invent missing facts."
            ),
        },
        {"role": "user", "content": text},
    ]


def draft_prompt(text: str, request_type: str, fields: IntakeFields, validation: IntakeValidation) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "Generate advisory CMMS draft text only. Return JSON only with this shape: "
                '{"draft_wo_description":"string","internal_note":"string","client_reply":"string"}. '
                "Do not claim a work order was created. Do not promise approval, dispatch, or email."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "original_text": text,
                    "request_type": request_type,
                    "fields": fields.model_dump(),
                    "validation": validation.model_dump(),
                }
            ),
        },
    ]


def record_usage_event(request: Request, status_code: int, duration_ms: float) -> None:
    if request.url.path in {"/api/system/logs"}:
        return
    try:
        db_execute(
            """
            INSERT INTO usage_events
            (timestamp, endpoint, method, status_code, duration_ms, client_host, key_id, key_name, user_id, environment_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_text(),
                request.url.path,
                request.method,
                status_code,
                duration_ms,
                request.client.host if request.client else "unknown",
                getattr(request.state, "api_key_id", None),
                getattr(request.state, "api_key_name", None),
                getattr(request.state, "user_id", None),
                getattr(request.state, "environment_code", None),
            ),
        )
    except Exception as exc:  # pragma: no cover - logging must never break API responses.
        logger.warning("usage_event_insert_failed error=%s", exc)


def redacted_summary(text: str, max_len: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned


def safe_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, default=str)


def parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return time.mktime(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def extract_result_value(response: dict[str, Any], field: str) -> Any:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    fields = response.get("fields") if isinstance(response.get("fields"), dict) else {}
    if field in result:
        return result.get(field)
    if field == "work_order_type":
        return result.get("work_order_type") or response.get("request_type")
    return fields.get(field)


async def execute_ai_endpoint_for_test(
    endpoint: str,
    input_text: str,
    environment_code: str | None,
    source: str = "test_case",
    prompt_id: int | None = None,
) -> dict[str, Any]:
    return await execute_ai_endpoint_for_test_helper(
        endpoint,
        input_text,
        environment_code,
        source=source,
        prompt_id=prompt_id,
        request_factory=ExtractFieldsRequest,
        call_ollama_func=call_ollama,
    )


@app.on_event("startup")
async def startup() -> None:
    init_database(
        seed_callbacks=[
            migrate_json_api_keys,
            bootstrap_admin_user,
            seed_default_environment,
            seed_default_output_contracts,
            seed_default_prompt_versions,
        ]
    )
    logger.info("service_start service=%s model=%s", SERVICE_NAME, MODEL_NAME)


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("service_shutdown service=%s", SERVICE_NAME)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        if request.url.path != "/api/system/logs":
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "api_call method=%s path=%s status=%s duration_ms=%.1f client=%s key_id=%s key_name=%s user=%s",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                request.client.host if request.client else "unknown",
                getattr(request.state, "api_key_id", "anonymous"),
                getattr(request.state, "api_key_name", "none"),
                getattr(request.state, "username", "none"),
            )
            record_usage_event(request, status_code, duration_ms)


@app.get("/api/prompt-versions/active/{endpoint}")
async def read_active_prompt_info(endpoint: str, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return active_prompt_info(endpoint)


@app.get("/api/admin/prompt-versions")
async def list_prompt_versions(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_prompt_versions_helper()


@app.get("/api/admin/prompt-versions/{endpoint}")
async def list_prompt_versions_for_endpoint(endpoint: str, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_prompt_versions_for_endpoint_helper(endpoint)


@app.post("/api/admin/prompt-versions")
async def create_prompt_version(payload: PromptVersionRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return create_prompt_version_helper(payload, user)


@app.patch("/api/admin/prompt-versions/{prompt_id}")
async def patch_prompt_version(prompt_id: int, payload: PromptVersionPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return patch_prompt_version_helper(prompt_id, payload, user)


@app.post("/api/admin/prompt-versions/{prompt_id}/promotion-check")
async def prompt_promotion_check(prompt_id: int, payload: PromotionCheckRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return check_prompt_promotion_gate(prompt_id, payload.comparison_id if payload else None)


@app.post("/api/admin/prompt-versions/{prompt_id}/activate")
async def activate_prompt_version(prompt_id: int, payload: PromptActivationRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return activate_prompt_version_helper(prompt_id, payload, user, PromptActivationRequest)


@app.post("/api/admin/prompt-versions/{prompt_id}/archive")
async def archive_prompt_version(prompt_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return archive_prompt_version_helper(prompt_id, user)


@app.post("/api/admin/prompt-versions/{prompt_id}/test")
async def test_prompt_version(prompt_id: int, payload: PromptTestRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await test_prompt_version_helper(
        prompt_id,
        payload,
        allowed_request_types=ALLOWED_REQUEST_TYPES,
        get_environment_values=get_environment_values,
        call_ollama=call_ollama,
    )


def test_case_runner_kwargs() -> dict[str, Any]:
    return {
        "endpoint_runner": execute_ai_endpoint_for_test,
        "prompt_row_for": prompt_row_for,
        "supported_prompt_endpoints": SUPPORTED_PROMPT_ENDPOINTS,
    }


def test_suite_runner_kwargs() -> dict[str, Any]:
    return {
        "run_test_case_row": run_test_case_row_helper,
        "prompt_row_for": prompt_row_for,
        "supported_prompt_endpoints": SUPPORTED_PROMPT_ENDPOINTS,
        "test_case_runner_kwargs": test_case_runner_kwargs(),
    }


async def run_test_case_row_for_prompt_comparison(
    row: sqlite3.Row,
    prompt_id: int | None = None,
    environment_override: str | None = None,
) -> dict[str, Any]:
    return await run_test_case_row_helper(
        row,
        prompt_id=prompt_id,
        environment_override=environment_override,
        **test_case_runner_kwargs(),
    )


@app.get("/api/admin/test-cases")
async def list_test_cases(
    endpoint: str | None = None,
    environment_code: str | None = None,
    enabled: bool | None = None,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_test_cases_helper(endpoint=endpoint, environment_code=environment_code, enabled=enabled)


@app.post("/api/admin/test-cases")
async def create_test_case(payload: TestCaseRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return create_test_case_helper(payload, user)


@app.get("/api/admin/test-cases/{test_case_id}")
async def get_test_case(test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    item = get_test_case_helper(test_case_id)
    if not item:
        raise HTTPException(status_code=404, detail="Test case not found")
    return item


@app.patch("/api/admin/test-cases/{test_case_id}")
async def patch_test_case(test_case_id: int, payload: TestCasePatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return patch_test_case_helper(test_case_id, payload, user)


@app.delete("/api/admin/test-cases/{test_case_id}")
async def delete_test_case(test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return delete_test_case_helper(test_case_id)


@app.post("/api/admin/test-cases/{test_case_id}/run")
async def run_test_case(test_case_id: int, payload: TestCaseRunRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await run_test_case_helper(test_case_id, payload, **test_case_runner_kwargs())


@app.post("/api/admin/test-cases/run-batch")
async def run_test_case_batch(payload: TestCaseBatchRunRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await run_test_case_batch_helper(payload, **test_case_runner_kwargs())


@app.get("/api/admin/test-case-runs")
async def list_test_case_runs(status: str | None = None, limit: int = 50, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_test_case_runs_helper(status=status, limit=limit)


@app.get("/api/admin/test-case-runs/{run_id}")
async def get_test_case_run(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    item = get_test_case_run_helper(run_id)
    if not item:
        raise HTTPException(status_code=404, detail="Test case run not found")
    return item


@app.get("/api/admin/test-suites")
async def list_test_suites(
    endpoint: str | None = None,
    environment_code: str | None = None,
    enabled: bool | None = None,
    required_for_promotion: bool | None = None,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_test_suites_helper(endpoint=endpoint, environment_code=environment_code, enabled=enabled, required_for_promotion=required_for_promotion)


@app.post("/api/admin/test-suites")
async def create_test_suite(payload: TestSuiteRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return create_test_suite_helper(payload, user)


@app.post("/api/admin/test-suites/run-batch")
async def run_test_suite_batch(payload: TestSuiteBatchRunRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await run_test_suite_batch_helper(payload, user, **test_suite_runner_kwargs())


@app.get("/api/admin/test-suite-runs")
async def list_test_suite_runs(status: str | None = None, limit: int = 50, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_test_suite_runs_helper(status=status, limit=limit)


@app.get("/api/admin/test-suite-runs/{suite_run_id}")
async def get_test_suite_run(suite_run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    item = get_test_suite_run_helper(suite_run_id)
    if not item:
        raise HTTPException(status_code=404, detail="Test suite run not found")
    return item


@app.get("/api/admin/test-suites/{suite_id}")
async def get_test_suite(suite_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return get_test_suite_helper(suite_id)


@app.patch("/api/admin/test-suites/{suite_id}")
async def patch_test_suite(suite_id: str, payload: TestSuitePatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return patch_test_suite_helper(suite_id, payload, user)


@app.delete("/api/admin/test-suites/{suite_id}")
async def delete_test_suite(suite_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return delete_test_suite_helper(suite_id)


@app.post("/api/admin/test-suites/{suite_id}/cases")
async def add_test_suite_case(suite_id: str, payload: TestSuiteCaseRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return add_test_suite_case_helper(suite_id, payload)


@app.delete("/api/admin/test-suites/{suite_id}/cases/{test_case_id}")
async def remove_test_suite_case(suite_id: str, test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return remove_test_suite_case_helper(suite_id, test_case_id)


@app.post("/api/admin/test-suites/{suite_id}/run")
async def run_test_suite(suite_id: str, payload: TestSuiteRunRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await run_test_suite_helper(suite_id, payload, user, **test_suite_runner_kwargs())


@app.get("/api/admin/regression-dashboard")
async def regression_dashboard(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return build_regression_dashboard()


@app.post("/api/admin/prompt-comparisons")
async def create_prompt_comparison(payload: PromptComparisonRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await run_prompt_comparison_helper(
        payload,
        user,
        prompt_version_by_id=prompt_version_by_id,
        run_test_case_row=run_test_case_row_for_prompt_comparison,
    )


@app.get("/api/admin/prompt-comparisons")
async def list_prompt_comparisons(
    endpoint: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_prompt_comparisons_helper(endpoint=endpoint, status=status, limit=limit)


@app.get("/api/admin/prompt-comparisons/{comparison_id}")
async def get_prompt_comparison(comparison_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    item = get_prompt_comparison_helper(comparison_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt comparison not found")
    return item


@app.get("/api/admin/prompt-promotions")
async def list_prompt_promotions(
    endpoint: str | None = None,
    limit: int = 50,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_prompt_promotions_helper(endpoint=endpoint, limit=limit)


@app.get("/api/admin/prompt-promotions/{promotion_id}")
async def get_prompt_promotion(promotion_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    item = get_prompt_promotion_helper(promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt promotion not found")
    return item


@app.get("/api/admin/api-keys")
async def list_api_keys(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    return list_api_keys_helper()


@app.post("/api/admin/api-keys")
async def create_api_key(payload: ApiKeyCreateRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return create_api_key_helper(payload, user)


@app.patch("/api/admin/api-keys/{key_id}")
async def patch_api_key(key_id: str, payload: ApiKeyPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return patch_api_key_helper(key_id, payload)


@app.get("/api/admin/logs", response_model=LogResponse)
async def admin_logs(lines: int = 200, user: PortalUser = Depends(current_user)) -> LogResponse:
    return LogResponse(log_file=str(LOG_FILE), lines=read_log_lines(lines))


@app.get("/api/admin/workflow-runs")
async def admin_workflow_runs(
    endpoint: str | None = None,
    environment_code: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    return list_workflow_runs(endpoint=endpoint, environment_code=environment_code, status=status, limit=limit)


@app.get("/api/admin/workflow-runs/{run_id}")
async def admin_workflow_run_detail(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    run = get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@app.post("/api/admin/workflow-runs/{run_id}/create-test-case")
async def create_test_case_from_workflow_run(
    run_id: str,
    payload: WorkflowRunCreateTestCaseRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    return await create_test_case_from_workflow_run_helper(run_id, payload, user)


@app.post("/api/admin/workflow-runs/{run_id}/replay")
async def replay_workflow_run(run_id: str, payload: TestCaseRunRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await replay_workflow_run_helper(run_id, payload, **test_case_runner_kwargs())


@app.get("/api/admin/reports/usage")
async def usage_report(user: PortalUser = Depends(current_user)) -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT endpoint, status_code, COALESCE(key_name, 'none') AS key_name,
               COALESCE(environment_code, '') AS environment_code,
               COUNT(*) AS calls, ROUND(AVG(duration_ms), 1) AS avg_duration_ms
        FROM usage_events
        GROUP BY endpoint, status_code, key_name, environment_code
        ORDER BY calls DESC, endpoint
        LIMIT 100
        """
    )
    return [dict(row) for row in rows]


@app.get("/api/admin/settings/{key}")
async def get_setting(key: str, user: PortalUser = Depends(current_admin)) -> dict[str, str]:
    row = db_fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return {"key": key, "value": row["value"] if row else ""}


@app.patch("/api/admin/settings/{key}")
async def patch_setting(key: str, payload: SettingPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, str]:
    db_execute(
        """
        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, payload.value, now_text()),
    )
    return {"status": "ok", "key": key}


@app.get("/api/system/status", response_model=SystemStatusResponse, dependencies=[Depends(require_local_control)])
async def system_status(user: PortalUser = Depends(current_admin)) -> SystemStatusResponse:
    return SystemStatusResponse(
        service=SERVICE_NAME,
        model=MODEL_NAME,
        api_running=True,
        ollama_running=await is_ollama_running(),
        log_file=str(LOG_FILE),
    )


@app.get("/api/system/logs", response_model=LogResponse, dependencies=[Depends(require_local_control)])
async def system_logs(lines: int = 200, user: PortalUser = Depends(current_user)) -> LogResponse:
    return LogResponse(log_file=str(LOG_FILE), lines=read_log_lines(lines))


@app.post("/api/system/ollama/start", dependencies=[Depends(require_local_control)])
async def start_ollama(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    if await is_ollama_running():
        return {"status": "ok", "ollama_running": True, "message": "Ollama is already running"}
    start_ollama_process()
    ollama_running = await wait_for_ollama()
    if not ollama_running:
        raise HTTPException(status_code=500, detail="Ollama did not become ready after startup")
    return {"status": "ok", "ollama_running": True, "message": "Ollama started"}


@app.post("/api/system/ollama/stop", dependencies=[Depends(require_local_control)])
async def stop_ollama(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    stop_ollama_process()
    return {"status": "ok", "ollama_running": await is_ollama_running()}


@app.post("/api/system/shutdown", dependencies=[Depends(require_local_control)])
async def shutdown_api(background_tasks: BackgroundTasks, user: PortalUser = Depends(current_admin)) -> dict[str, str]:
    background_tasks.add_task(shutdown_process_later)
    return {"status": "stopping", "message": "FastAPI service is stopping"}


@app.post("/api/ai/summarize-work-order", response_model=SummaryResponse, dependencies=[Depends(require_api_key)])
async def summarize_work_order(request: Request, payload: TextRequest) -> SummaryResponse:
    if payload.environment_code:
        request.state.environment_code = payload.environment_code
    return await summarize_work_order_helper(payload, call_ollama_func=call_ollama)


@app.post("/api/ai/cmms-assistant", response_model=AssistantResponse, dependencies=[Depends(require_api_key)])
async def cmms_assistant(request: Request, payload: TextRequest) -> AssistantResponse:
    if payload.environment_code:
        request.state.environment_code = payload.environment_code
    return await cmms_assistant_helper(payload, call_ollama_func=call_ollama)


@app.post("/api/ai/extract-work-order-fields", response_model=ExtractFieldsResponse, dependencies=[Depends(require_api_key)])
async def extract_work_order_fields(request: Request, payload: ExtractFieldsRequest) -> ExtractFieldsResponse:
    result = await extract_work_order_fields_helper(payload, call_ollama_func=call_ollama)
    env_code = result.pop("_environment_code", None)
    if env_code:
        request.state.environment_code = env_code
    return result


@app.post("/api/ai/cmms-intake", response_model=IntakeResponse, dependencies=[Depends(require_api_key)])
async def cmms_intake(request: Request, payload: ExtractFieldsRequest) -> IntakeResponse:
    result = await cmms_intake_helper(
        payload,
        user_id=getattr(request.state, "user_id", None),
        api_key_id=getattr(request.state, "api_key_id", None),
        call_ollama_func=call_ollama,
    )
    if result.get("environment_code"):
        request.state.environment_code = result["environment_code"]
    return result


@app.post("/api/ai/intake/email", response_model=IntakeResponse, dependencies=[Depends(require_api_key)])
async def email_intake(request: Request, payload: EmailIntakeRequest) -> IntakeResponse:
    text = build_email_intake_text(
        from_email=payload.from_email,
        to_email=payload.to_email,
        subject=payload.subject,
        body=payload.body,
    )
    if len(text) > 4000:
        raise HTTPException(status_code=422, detail="Email intake content must be 4000 characters or fewer after formatting")
    intake_payload = ExtractFieldsRequest(
        text=text,
        environment_code=payload.environment_code,
        source="email_api",
        submission=SubmissionMetadata(
            submitted_by=payload.submitted_by,
            submitted_email=payload.from_email,
            submitted_phone=payload.submitted_phone,
            submitted_at=payload.submitted_at,
            submitted_method="email_api",
        ),
        request=IntakeRequestMetadata(
            requested_due_at=payload.requested_due_at,
            location=payload.location,
        ),
    )
    result = await cmms_intake_helper(
        intake_payload,
        user_id=getattr(request.state, "user_id", None),
        api_key_id=getattr(request.state, "api_key_id", None),
        source="email_api",
        call_ollama_func=call_ollama,
    )
    if result.get("environment_code"):
        request.state.environment_code = result["environment_code"]
    return result
