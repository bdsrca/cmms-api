import asyncio
import csv
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import subprocess
import threading
import time
from io import StringIO
from typing import Any

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .db import (
    API_KEYS_JSON,
    BASE_DIR,
    DATA_DIR,
    DB_LOCK,
    LOG_DIR,
    LOG_FILE,
    db_connect,
    db_execute,
    db_fetchall,
    db_fetchone,
)
from .regression_dashboard import build_regression_dashboard
from .workflow_trace import (
    cleanup_workflow_runs,
    fail_workflow_step,
    finish_workflow_run,
    finish_workflow_step,
    get_workflow_run,
    list_workflow_runs,
    start_workflow_run,
    start_workflow_step,
)


MODEL_NAME = "qwen3:8b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
SERVICE_NAME = "local-cmms-llm-api"
ADVISORY_WARNING = "Advisory mode only. No CMMS write-back was performed."
SESSION_COOKIE = "cmms_portal_session"
SESSION_TTL_SECONDS = 8 * 60 * 60

LOGIN_LOCK = threading.Lock()
LOGIN_FAILURES: dict[str, dict[str, Any]] = {}
LOGIN_WINDOW_SECONDS = 10 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5
DISALLOWED_ADMIN_PASSWORDS = {"change-this-password", "password", "admin", "admin123", "my-secret-key"}
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

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


class HealthResponse(BaseModel):
    status: str
    service: str
    model: str


class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None
    source: str | None = None


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
    raw: dict[str, Any] | None = None
    request_type: str | None = None
    classification_confidence: float | None = None
    fields: IntakeFields | None = None
    validation: IntakeValidation | None = None
    drafts: IntakeDrafts | None = None
    model: str


class AuthContext(BaseModel):
    key_id: str
    name: str
    is_admin: bool
    source: str


class PortalUser(BaseModel):
    user_id: int
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = Field(default="user", pattern="^(admin|user)$")


class UserPatchRequest(BaseModel):
    enabled: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)
    role: str | None = Field(default=None, pattern="^(admin|user)$")


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    owner: str | None = None


class ApiKeyPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None


class EnvironmentRequest(BaseModel):
    environment_code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    enabled: bool = True


class EnvironmentPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None


class CodeImportRequest(BaseModel):
    category: str
    values: list[str] | None = None
    text: str | None = None
    replace: bool = True


class CodeValuePatchRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=240)
    aliases: str | None = Field(default=None, max_length=500)
    metadata_json: str | None = None
    enabled: bool | None = None


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


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_disallowed_admin_password(password: str) -> bool:
    return password.strip() in DISALLOWED_ADMIN_PASSWORDS or len(password.strip()) < 12


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("$argon2"):
        try:
            return PASSWORD_HASHER.verify(stored, password)
        except (VerifyMismatchError, VerificationError):
            return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _algorithm, salt, expected = stored.split("$", 2)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
        return hmac.compare_digest(digest.hex(), expected)
    return False


def password_needs_rehash(stored: str) -> bool:
    if not stored.startswith("$argon2"):
        return True
    try:
        return PASSWORD_HASHER.check_needs_rehash(stored)
    except VerificationError:
        return True


def login_rate_key(request: Request, username: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username.strip().lower()}"


def check_login_rate_limit(request: Request, username: str) -> None:
    key = login_rate_key(request, username)
    now = time.time()
    with LOGIN_LOCK:
        state = LOGIN_FAILURES.get(key)
        if not state:
            return
        if state.get("locked_until", 0) > now:
            raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again later.")
        if now - state.get("first_failed_at", now) > LOGIN_WINDOW_SECONDS:
            LOGIN_FAILURES.pop(key, None)


def record_login_failure(request: Request, username: str) -> None:
    key = login_rate_key(request, username)
    now = time.time()
    with LOGIN_LOCK:
        state = LOGIN_FAILURES.get(key)
        if not state or now - state.get("first_failed_at", now) > LOGIN_WINDOW_SECONDS:
            state = {"count": 0, "first_failed_at": now, "locked_until": 0}
        state["count"] += 1
        if state["count"] >= LOGIN_MAX_FAILURES:
            state["locked_until"] = now + LOGIN_LOCKOUT_SECONDS
        LOGIN_FAILURES[key] = state


def clear_login_failures(request: Request, username: str) -> None:
    with LOGIN_LOCK:
        LOGIN_FAILURES.pop(login_rate_key(request, username), None)


def should_use_secure_cookie(request: Request) -> bool:
    env_value = os.getenv("PORTAL_COOKIE_SECURE", "").strip().lower()
    if env_value in {"1", "true", "yes"}:
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    return request.url.scheme == "https" or "https" in forwarded_proto


def init_db() -> None:
    schema = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            enabled INTEGER NOT NULL DEFAULT 1,
            owner TEXT,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            usage_count INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS environments (
            environment_code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS code_values (
            code_id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_code TEXT NOT NULL,
            category TEXT NOT NULL,
            code TEXT NOT NULL,
            label TEXT NOT NULL,
            aliases TEXT,
            metadata_json TEXT,
            source TEXT NOT NULL DEFAULT 'Manual',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(environment_code, category, code),
            FOREIGN KEY(environment_code) REFERENCES environments(environment_code)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS environment_validation_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_code TEXT NOT NULL,
            field_name TEXT NOT NULL,
            label TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            required INTEGER NOT NULL DEFAULT 0,
            code_category TEXT,
            must_match_code_list INTEGER NOT NULL DEFAULT 0,
            allow_unknown INTEGER NOT NULL DEFAULT 0,
            severity TEXT NOT NULL DEFAULT 'warning' CHECK(severity IN ('error', 'warning')),
            sort_order INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(environment_code, field_name),
            FOREIGN KEY(environment_code) REFERENCES environments(environment_code)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_output_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            version TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'active', 'archived')),
            schema_json TEXT NOT NULL,
            strict_mode INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER,
            UNIQUE(endpoint, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS usage_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            duration_ms REAL NOT NULL,
            client_host TEXT,
            key_id TEXT,
            key_name TEXT,
            user_id INTEGER,
            environment_code TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            version TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'active', 'archived')),
            system_prompt TEXT NOT NULL,
            user_template TEXT NOT NULL,
            model TEXT NOT NULL,
            temperature REAL NOT NULL DEFAULT 0.1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER,
            UNIQUE(endpoint, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            environment_code TEXT,
            input_text TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            expected_json TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            tags TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_test_case_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_case_id INTEGER,
            run_id TEXT,
            endpoint TEXT NOT NULL,
            environment_code TEXT,
            prompt_id INTEGER,
            prompt_version TEXT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            actual_json TEXT,
            comparison_json TEXT,
            error_message TEXT,
            FOREIGN KEY(test_case_id) REFERENCES ai_test_cases(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_test_suites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suite_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            environment_code TEXT,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            required_for_promotion INTEGER NOT NULL DEFAULT 0,
            min_pass_rate REAL NOT NULL DEFAULT 1.0,
            zero_regression_required INTEGER NOT NULL DEFAULT 1,
            zero_error_required INTEGER NOT NULL DEFAULT 1,
            tags TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by INTEGER,
            updated_by INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_test_suite_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suite_id TEXT NOT NULL,
            test_case_id INTEGER NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            UNIQUE(suite_id, test_case_id),
            FOREIGN KEY(suite_id) REFERENCES ai_test_suites(suite_id),
            FOREIGN KEY(test_case_id) REFERENCES ai_test_cases(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_test_suite_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suite_run_id TEXT NOT NULL UNIQUE,
            suite_id TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            environment_code TEXT,
            prompt_id INTEGER,
            prompt_version TEXT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            summary_json TEXT,
            created_by INTEGER,
            FOREIGN KEY(suite_id) REFERENCES ai_test_suites(suite_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_test_suite_run_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suite_run_id TEXT NOT NULL,
            test_case_id INTEGER NOT NULL,
            test_case_run_id INTEGER,
            status TEXT NOT NULL,
            comparison_json TEXT,
            FOREIGN KEY(suite_run_id) REFERENCES ai_test_suite_runs(suite_run_id),
            FOREIGN KEY(test_case_id) REFERENCES ai_test_cases(id),
            FOREIGN KEY(test_case_run_id) REFERENCES ai_test_case_runs(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comparison_id TEXT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            environment_code TEXT,
            baseline_prompt_id INTEGER NOT NULL,
            candidate_prompt_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            summary_json TEXT,
            created_by INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_comparison_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comparison_id TEXT NOT NULL,
            test_case_id INTEGER NOT NULL,
            baseline_run_id TEXT,
            candidate_run_id TEXT,
            baseline_status TEXT NOT NULL,
            candidate_status TEXT NOT NULL,
            result TEXT NOT NULL CHECK(result IN ('improved', 'regressed', 'unchanged_pass', 'unchanged_fail', 'error')),
            comparison_json TEXT,
            FOREIGN KEY(comparison_id) REFERENCES ai_prompt_comparisons(comparison_id),
            FOREIGN KEY(test_case_id) REFERENCES ai_test_cases(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promotion_id TEXT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            previous_prompt_id INTEGER,
            promoted_prompt_id INTEGER NOT NULL,
            comparison_id TEXT,
            gate_status TEXT NOT NULL CHECK(gate_status IN ('passed', 'blocked', 'overridden')),
            override_used INTEGER NOT NULL DEFAULT 0,
            override_reason TEXT,
            promoted_by INTEGER,
            promoted_at TEXT NOT NULL,
            summary_json TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            environment_code TEXT,
            user_id INTEGER,
            api_key_id TEXT,
            source TEXT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            error_message TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS workflow_run_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            status TEXT NOT NULL,
            model TEXT,
            prompt_version TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            input_summary TEXT,
            output_summary TEXT,
            output_json TEXT,
            error_message TEXT,
            FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_at ON workflow_runs(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_runs_endpoint ON workflow_runs(endpoint)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_runs_environment ON workflow_runs(environment_code)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_run_id ON workflow_run_steps(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_versions_endpoint_status ON ai_prompt_versions(endpoint, status)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_cases_endpoint ON ai_test_cases(endpoint)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_cases_environment ON ai_test_cases(environment_code)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_cases_enabled ON ai_test_cases(enabled)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_case_runs_test_case_id ON ai_test_case_runs(test_case_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_case_runs_started_at ON ai_test_case_runs(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_case_runs_status ON ai_test_case_runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suites_endpoint ON ai_test_suites(endpoint)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suites_environment ON ai_test_suites(environment_code)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suites_enabled ON ai_test_suites(enabled)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suites_required_for_promotion ON ai_test_suites(required_for_promotion)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suite_cases_suite_id ON ai_test_suite_cases(suite_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suite_cases_test_case_id ON ai_test_suite_cases(test_case_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suite_runs_suite_id ON ai_test_suite_runs(suite_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suite_runs_started_at ON ai_test_suite_runs(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suite_runs_status ON ai_test_suite_runs(status)",
        "CREATE INDEX IF NOT EXISTS idx_ai_test_suite_run_cases_suite_run_id ON ai_test_suite_run_cases(suite_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_comparisons_endpoint ON ai_prompt_comparisons(endpoint)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_comparisons_started_at ON ai_prompt_comparisons(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_comparisons_status ON ai_prompt_comparisons(status)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_comparison_cases_comparison_id ON ai_prompt_comparison_cases(comparison_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_comparison_cases_test_case_id ON ai_prompt_comparison_cases(test_case_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_comparison_cases_result ON ai_prompt_comparison_cases(result)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_promotions_endpoint ON ai_prompt_promotions(endpoint)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_promotions_promoted_at ON ai_prompt_promotions(promoted_at)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_promotions_promoted_prompt_id ON ai_prompt_promotions(promoted_prompt_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_prompt_promotions_comparison_id ON ai_prompt_promotions(comparison_id)",
    ]
    with DB_LOCK:
        with db_connect() as conn:
            for statement in schema:
                conn.execute(statement)
            ensure_schema_columns(conn)
            conn.commit()
    migrate_json_api_keys()
    bootstrap_admin_user()
    seed_default_environment()
    seed_default_output_contracts()
    seed_default_prompt_versions()


def ensure_schema_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(code_values)").fetchall()}
    migrations = {
        "aliases": "ALTER TABLE code_values ADD COLUMN aliases TEXT",
        "metadata_json": "ALTER TABLE code_values ADD COLUMN metadata_json TEXT",
        "source": "ALTER TABLE code_values ADD COLUMN source TEXT NOT NULL DEFAULT 'Manual'",
        "updated_at": "ALTER TABLE code_values ADD COLUMN updated_at TEXT",
    }
    for column, statement in migrations.items():
        if column not in columns:
            conn.execute(statement)
    conn.execute("UPDATE code_values SET updated_at = COALESCE(updated_at, created_at, ?)", (now_text(),))


def migrate_json_api_keys() -> None:
    if not API_KEYS_JSON.exists():
        return
    try:
        data = json.loads(API_KEYS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("api_keys_json_migration skipped=invalid_json")
        return
    for record in data.get("keys", []):
        if not record.get("key_id") or not record.get("key_hash"):
            continue
        db_execute(
            """
            INSERT OR IGNORE INTO api_keys
            (key_id, name, key_hash, enabled, owner, created_at, last_used_at, usage_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["key_id"],
                record.get("name") or record["key_id"],
                record["key_hash"],
                1 if record.get("enabled", True) else 0,
                record.get("owner"),
                record.get("created_at") or now_text(),
                record.get("last_used_at"),
                int(record.get("usage_count") or 0),
            ),
        )


def bootstrap_admin_user() -> None:
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        logger.warning("admin_bootstrap_missing ADMIN_USERNAME/ADMIN_PASSWORD not set")
        return
    if is_disallowed_admin_password(password):
        logger.error("admin_bootstrap_rejected reason=weak_or_default_password username=%s", username.strip())
        return
    existing_user = db_fetchone("SELECT * FROM users WHERE username = ?", (username.strip(),))
    if existing_user:
        if existing_user["role"] != "admin" or password_needs_rehash(existing_user["password_hash"]):
            db_execute(
                "UPDATE users SET password_hash = ?, role = 'admin', enabled = 1 WHERE user_id = ?",
                (hash_password(password), existing_user["user_id"]),
            )
            logger.info("admin_bootstrap_updated username=%s", username.strip())
        return
    admin_count = db_fetchone("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
    if admin_count and admin_count["count"] > 0:
        return
    db_execute(
        """
        INSERT INTO users (username, password_hash, role, enabled, created_at)
        VALUES (?, ?, 'admin', 1, ?)
        """,
        (username.strip(), hash_password(password), now_text()),
    )
    logger.info("admin_bootstrap_created username=%s", username.strip())


def seed_default_environment() -> None:
    exists = db_fetchone("SELECT environment_code FROM environments WHERE environment_code = 'DEFAULT'")
    if exists:
        return
    timestamp = now_text()
    db_execute(
        "INSERT INTO environments (environment_code, name, enabled, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
        ("DEFAULT", "Default local test", timestamp, timestamp),
    )
    defaults = {
        "buildings": ["ARC", "CAMPUSVIEW", "ZONE-18"],
        "rooms": ["205", "301", "110"],
        "priorities": ["LOW", "NORMAL", "URGENT"],
        "work_order_types": sorted(ALLOWED_REQUEST_TYPES - {"Unknown"}),
        "assign_to": ["Facilities"],
        "issue_to_employee_number": ["0000"],
        "job_type": ["Maintenance"],
    }
    for category, values in defaults.items():
        import_code_values("DEFAULT", category, values, replace=False)
    reset_validation_rules("DEFAULT")


def reset_validation_rules(environment_code: str) -> None:
    timestamp = now_text()
    with DB_LOCK:
        with db_connect() as conn:
            conn.execute("DELETE FROM environment_validation_rules WHERE environment_code = ?", (environment_code,))
            for field_name, label, required, category, must_match, allow_unknown, severity, sort_order in DEFAULT_VALIDATION_RULES:
                conn.execute(
                    """
                    INSERT INTO environment_validation_rules
                    (environment_code, field_name, label, enabled, required, code_category,
                     must_match_code_list, allow_unknown, severity, sort_order, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        environment_code,
                        field_name,
                        label,
                        1 if required else 0,
                        category,
                        1 if must_match else 0,
                        1 if allow_unknown else 0,
                        severity,
                        sort_order,
                        timestamp,
                    ),
                )
            conn.commit()


def ensure_validation_rules(environment_code: str) -> None:
    count = db_fetchone(
        "SELECT COUNT(*) AS count FROM environment_validation_rules WHERE environment_code = ?",
        (environment_code,),
    )
    if not count or count["count"] == 0:
        reset_validation_rules(environment_code)


def seed_default_output_contracts() -> None:
    row = db_fetchone(
        "SELECT id FROM ai_output_contracts WHERE endpoint = ? AND version = ?",
        ("cmms-intake", "v1"),
    )
    if row:
        return
    timestamp = now_text()
    db_execute(
        """
        INSERT INTO ai_output_contracts
        (endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at)
        VALUES (?, ?, ?, 'active', ?, 1, ?, ?)
        """,
        (
            "cmms-intake",
            "v1",
            "Default CMMS intake output contract",
            json.dumps(DEFAULT_CMMS_INTAKE_CONTRACT),
            timestamp,
            timestamp,
        ),
    )


def seed_default_prompt_versions() -> None:
    timestamp = now_text()
    for endpoint, spec in DEFAULT_PROMPT_VERSIONS.items():
        row = db_fetchone(
            "SELECT id FROM ai_prompt_versions WHERE endpoint = ? AND version = ?",
            (endpoint, spec["version"]),
        )
        if row:
            continue
        db_execute(
            """
            INSERT INTO ai_prompt_versions
            (endpoint, version, name, status, system_prompt, user_template, model, temperature, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                endpoint,
                spec["version"],
                spec["name"],
                spec["system_prompt"],
                spec["user_template"],
                MODEL_NAME,
                float(spec["temperature"]),
                timestamp,
                timestamp,
            ),
        )


def import_code_values(environment_code: str, category: str, values: list[str], replace: bool) -> int:
    if category not in CODE_CATEGORIES and not category.startswith("custom:"):
        raise HTTPException(status_code=400, detail="Invalid code category")
    cleaned = []
    seen = set()
    for value in values:
        code = str(value).strip()
        if code and code not in seen:
            cleaned.append(code)
            seen.add(code)
    with DB_LOCK:
        with db_connect() as conn:
            if replace:
                conn.execute(
                    "DELETE FROM code_values WHERE environment_code = ? AND category = ?",
                    (environment_code, category),
                )
            for code in cleaned:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO code_values
                    (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, NULL, NULL, 'Manual', 1, ?, ?)
                    """,
                    (environment_code, category, code, code, now_text(), now_text()),
                )
            conn.commit()
    return len(cleaned)


def parse_code_text(text: str) -> list[str]:
    return [row["code"] for row in parse_code_rows(text)]


def parse_code_rows(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []
    values: list[dict[str, str]] = []
    reader = csv.reader(StringIO(text))
    for row in reader:
        if not row:
            continue
        code = row[0].strip() if len(row) > 0 else ""
        if not code:
            continue
        values.append(
            {
                "code": code,
                "label": row[1].strip() if len(row) > 1 and row[1].strip() else code,
                "aliases": row[2].strip() if len(row) > 2 else "",
                "metadata_json": row[3].strip() if len(row) > 3 else "",
            }
        )
    return values


def preview_code_import(environment_code: str, category: str, text: str) -> dict[str, Any]:
    rows = parse_code_rows(text)
    existing_rows = db_fetchall(
        "SELECT code FROM code_values WHERE environment_code = ? AND category = ?",
        (environment_code, category),
    )
    existing = {row["code"] for row in existing_rows}
    seen: set[str] = set()
    valid = []
    duplicates = []
    invalid = []
    for row in rows:
        code = row["code"]
        if not code:
            invalid.append(row)
        elif code in seen:
            duplicates.append(row)
        else:
            valid.append(row)
            seen.add(code)
    updates = [row for row in valid if row["code"] in existing]
    inserts = [row for row in valid if row["code"] not in existing]
    return {
        "environment_code": environment_code,
        "category": category,
        "valid_count": len(valid),
        "duplicate_count": len(duplicates),
        "invalid_count": len(invalid),
        "update_count": len(updates),
        "insert_count": len(inserts),
        "valid": valid,
        "duplicates": duplicates,
        "invalid": invalid,
    }


def import_code_rows(environment_code: str, category: str, rows: list[dict[str, str]], replace: bool) -> int:
    if category not in CODE_CATEGORIES and not category.startswith("custom:"):
        raise HTTPException(status_code=400, detail="Invalid code category")
    timestamp = now_text()
    count = 0
    seen: set[str] = set()
    with DB_LOCK:
        with db_connect() as conn:
            if replace:
                conn.execute(
                    "DELETE FROM code_values WHERE environment_code = ? AND category = ?",
                    (environment_code, category),
                )
            for row in rows:
                code = row["code"].strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                metadata = row.get("metadata_json") or None
                if metadata:
                    try:
                        json.loads(metadata)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON for {code}") from exc
                conn.execute(
                    """
                    INSERT INTO code_values
                    (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'Import', 1, ?, ?)
                    ON CONFLICT(environment_code, category, code)
                    DO UPDATE SET label = excluded.label, aliases = excluded.aliases,
                                  metadata_json = excluded.metadata_json, source = excluded.source,
                                  enabled = 1, updated_at = excluded.updated_at
                    """,
                    (
                        environment_code,
                        category,
                        code,
                        row.get("label") or code,
                        row.get("aliases") or None,
                        metadata,
                        timestamp,
                        timestamp,
                    ),
                )
                count += 1
            conn.commit()
    return count


def get_environment_values(environment_code: str) -> dict[str, list[str]]:
    env = db_fetchone(
        "SELECT environment_code FROM environments WHERE environment_code = ? AND enabled = 1",
        (environment_code,),
    )
    if not env:
        raise HTTPException(status_code=400, detail="Invalid or disabled environment_code")
    rows = db_fetchall(
        """
        SELECT category, code FROM code_values
        WHERE environment_code = ? AND enabled = 1
        ORDER BY category, code
        """,
        (environment_code,),
    )
    values: dict[str, list[str]] = {category: [] for category in CODE_CATEGORIES}
    for row in rows:
        values.setdefault(row["category"], []).append(row["code"])
    return values


def get_validation_rules(environment_code: str) -> list[dict[str, Any]]:
    ensure_validation_rules(environment_code)
    rows = db_fetchall(
        """
        SELECT id, environment_code, field_name, label, enabled, required, code_category,
               must_match_code_list, allow_unknown, severity, sort_order, updated_at
        FROM environment_validation_rules
        WHERE environment_code = ?
        ORDER BY sort_order, field_name
        """,
        (environment_code,),
    )
    return [dict(row) for row in rows]


def build_code_lookup(environment_code: str, category: str | None) -> dict[str, str]:
    if not category:
        return {}
    rows = db_fetchall(
        """
        SELECT code, label, aliases FROM code_values
        WHERE environment_code = ? AND category = ? AND enabled = 1
        """,
        (environment_code, category),
    )
    lookup: dict[str, str] = {}
    for row in rows:
        code = str(row["code"])
        candidates = [code, row["label"]]
        aliases = row["aliases"] or ""
        candidates.extend(part.strip() for part in aliases.split(",") if part.strip())
        for candidate in candidates:
            if candidate:
                lookup[candidate.strip().casefold()] = code
    return lookup


def validation_issue(field: str, value: Any, message: str) -> dict[str, Any]:
    return {"field": field, "value": value, "message": message}


def validate_ai_output(environment_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    rules = get_validation_rules(environment_code)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized: dict[str, Any] = {}

    for rule in rules:
        if not rule["enabled"]:
            continue
        field = rule["field_name"]
        value = payload.get(field)
        value_text = str(value).strip() if value is not None else ""
        issues = errors if rule["severity"] == "error" else warnings

        if rule["required"] and not value_text:
            issues.append(validation_issue(field, value, f"{rule['label']} is required for environment {environment_code}."))
            continue
        if not value_text:
            continue

        if rule["must_match_code_list"]:
            lookup = build_code_lookup(environment_code, rule["code_category"])
            matched_code = lookup.get(value_text.casefold())
            if matched_code:
                normalized[field] = matched_code
            elif not rule["allow_unknown"]:
                issues.append(
                    validation_issue(
                        field,
                        value,
                        f"{rule['label']} is not in the configured code list for environment {environment_code}.",
                    )
                )
            else:
                normalized[field] = value
        else:
            normalized[field] = value

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "normalized": normalized,
    }


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def type_matches(value: Any, expected: Any) -> bool:
    expected_types = expected if isinstance(expected, list) else [expected]
    actual = json_type_name(value)
    if actual == "number" and "integer" in expected_types and isinstance(value, int) and not isinstance(value, bool):
        return True
    return actual in expected_types


def active_contract(endpoint: str) -> sqlite3.Row | None:
    return db_fetchone(
        "SELECT * FROM ai_output_contracts WHERE endpoint = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (endpoint,),
    )


def active_prompt_version(endpoint: str) -> sqlite3.Row:
    if endpoint not in SUPPORTED_PROMPT_ENDPOINTS:
        raise HTTPException(status_code=400, detail="Unsupported prompt endpoint")
    row = db_fetchone(
        "SELECT * FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (endpoint,),
    )
    if row:
        return row
    seed_default_prompt_versions()
    row = db_fetchone(
        "SELECT * FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (endpoint,),
    )
    if not row:
        raise HTTPException(status_code=500, detail=f"No active prompt configured for {endpoint}")
    return row


def prompt_version_by_id(prompt_id: int) -> sqlite3.Row:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return row


def prompt_row_for(endpoint: str, prompt_id: int | None = None) -> sqlite3.Row:
    if prompt_id is not None:
        row = prompt_version_by_id(prompt_id)
        if row["endpoint"] != endpoint:
            raise HTTPException(status_code=400, detail="Prompt endpoint does not match requested endpoint")
        return row
    return active_prompt_version(endpoint)


def render_prompt_template(template: str, context: dict[str, Any]) -> str:
    rendered = template
    for key, value in context.items():
        if isinstance(value, str):
            replacement = value
        else:
            replacement = json.dumps(value, ensure_ascii=False)
        rendered = rendered.replace("{{" + key + "}}", replacement)
    return rendered


def prompt_metadata(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "prompt_id": row["id"],
        "prompt_version": row["version"],
        "model": row["model"],
        "temperature": float(row["temperature"]),
    }


def prompt_messages(endpoint: str, context: dict[str, Any], prompt_id: int | None = None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    row = prompt_row_for(endpoint, prompt_id)
    system_prompt = render_prompt_template(row["system_prompt"], context)
    user_prompt = render_prompt_template(row["user_template"], context)
    return ([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], prompt_metadata(row))


def intake_prompt_messages(context: dict[str, Any], prompt_id: int | None = None) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    row = prompt_row_for("cmms-intake", prompt_id)
    try:
        parts = json.loads(row["system_prompt"])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Active cmms-intake prompt contains invalid JSON") from exc
    required = {"classifier", "field_extractor", "draft_generator"}
    if not required.issubset(parts):
        raise HTTPException(status_code=500, detail="Active cmms-intake prompt is missing required prompt parts")
    user_text = render_prompt_template(row["user_template"], context)
    messages = {
        name: [{"role": "system", "content": render_prompt_template(parts[name], context)}, {"role": "user", "content": user_text}]
        for name in required
    }
    return messages, prompt_metadata(row)


def validate_output_contract(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    contract = active_contract(endpoint)
    if not contract:
        return {
            "valid": True,
            "errors": [],
            "warnings": ["No active output contract configured."],
            "contract_version": None,
            "normalized_payload": payload,
        }
    try:
        schema = json.loads(contract["schema_json"])
    except json.JSONDecodeError:
        return {
            "valid": False,
            "errors": ["Active output contract contains invalid schema JSON."],
            "warnings": [],
            "contract_version": contract["version"],
            "normalized_payload": {},
        }

    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, Any] = {}

    if schema.get("type") == "object" and not isinstance(payload, dict):
        errors.append(f"Payload must be object, got {json_type_name(payload)}.")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "contract_version": contract["version"],
            "normalized_payload": {},
        }

    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    for field in required:
        if field not in payload or payload.get(field) is None:
            errors.append(f"Missing required field: {field}")

    for field, value in payload.items():
        field_schema = properties.get(field)
        if not field_schema:
            message = f"Additional property not allowed: {field}"
            if contract["strict_mode"]:
                errors.append(message)
            else:
                warnings.append(message)
                normalized[field] = value
            continue
        if "type" in field_schema and not type_matches(value, field_schema["type"]):
            errors.append(f"Field {field} must be {field_schema['type']}, got {json_type_name(value)}")
            continue
        normalized[field] = value

    for field in properties:
        if field not in normalized and field in payload:
            normalized[field] = payload[field]

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "contract_version": contract["version"],
        "normalized_payload": normalized if len(errors) == 0 else {},
    }


def skipped_ai_validation() -> dict[str, Any]:
    return {
        "enabled": True,
        "valid": None,
        "status": "not_run",
        "message": "Skipped because output contract validation failed.",
        "errors": [],
        "warnings": [],
        "normalized": {},
    }


def resolve_validation_lists(request: ExtractFieldsRequest | TextRequest) -> tuple[list[str], list[str], str | None]:
    if request.environment_code:
        values = get_environment_values(request.environment_code)
        buildings = values.get("buildings") or []
        priorities = values.get("priorities") or ["NORMAL"]
        return buildings, priorities, request.environment_code
    if isinstance(request, ExtractFieldsRequest):
        if not request.valid_buildings:
            raise HTTPException(status_code=422, detail="valid_buildings is required when environment_code is not provided")
        if not request.valid_priorities:
            raise HTTPException(status_code=422, detail="valid_priorities is required when environment_code is not provided")
        return request.valid_buildings, request.valid_priorities, None
    return [], [], None


def session_user_from_token(token: str) -> PortalUser | None:
    token_hash = hash_text(token)
    row = db_fetchone(
        """
        SELECT u.user_id, u.username, u.role, u.enabled, s.expires_at
        FROM sessions s
        JOIN users u ON u.user_id = s.user_id
        WHERE s.token_hash = ?
        """,
        (token_hash,),
    )
    if not row or not row["enabled"] or int(row["expires_at"]) < int(time.time()):
        return None
    return PortalUser(user_id=row["user_id"], username=row["username"], role=row["role"])


def current_user(request: Request) -> PortalUser:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    user = session_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    request.state.user_id = user.user_id
    request.state.username = user.username
    return user


def current_admin(user: PortalUser = Depends(current_user)) -> PortalUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_local_control(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="System controls are local-only")


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> AuthContext:
    expected_key = os.getenv("LLM_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="LLM_API_KEY environment variable is not set")
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if secrets.compare_digest(x_api_key, expected_key):
        auth = AuthContext(key_id="env-admin", name="Environment admin key", is_admin=True, source="env")
        request.state.api_key_id = auth.key_id
        request.state.api_key_name = auth.name
        return auth

    incoming_hash = hash_text(x_api_key)
    row = db_fetchone(
        "SELECT key_id, name, enabled FROM api_keys WHERE key_hash = ?",
        (incoming_hash,),
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if not row["enabled"]:
        raise HTTPException(status_code=401, detail="API key is disabled")
    db_execute(
        "UPDATE api_keys SET usage_count = usage_count + 1, last_used_at = ? WHERE key_id = ?",
        (now_text(), row["key_id"]),
    )
    auth = AuthContext(key_id=row["key_id"], name=row["name"], is_admin=False, source="generated")
    request.state.api_key_id = auth.key_id
    request.state.api_key_name = auth.name
    return auth


def normalize_allowed_values(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def normalize_missing_fields(fields: Any) -> list[str]:
    if not isinstance(fields, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, str):
            continue
        cleaned = field.strip()
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return normalized


def ensure_missing_field(missing_fields: list[str], field: str) -> None:
    if field not in missing_fields:
        missing_fields.append(field)


def parse_json_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Model returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="Model returned invalid JSON")
    return parsed


async def call_ollama(
    messages: list[dict[str, str]],
    timeout: int = 120,
    temperature: float | None = None,
    model: str = MODEL_NAME,
) -> str:
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(OLLAMA_CHAT_URL, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail="Ollama request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to Ollama") from exc
    try:
        data = response.json()
        content = data["message"]["content"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Ollama returned an unexpected response") from exc
    if not isinstance(content, str):
        raise HTTPException(status_code=502, detail="Ollama returned an unexpected response")
    return content.strip()


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


def validate_extracted_fields(
    data: dict[str, Any],
    valid_buildings: list[str],
    valid_priorities: list[str],
) -> ExtractFieldsResponse:
    allowed_buildings = set(normalize_allowed_values(valid_buildings))
    allowed_priorities = set(normalize_allowed_values(valid_priorities))

    request_type = data.get("request_type")
    if request_type not in ALLOWED_REQUEST_TYPES:
        request_type = "Unknown"

    building = data.get("building")
    building = building.strip() if isinstance(building, str) else None
    building = building or None

    room = data.get("room")
    room = room.strip() if isinstance(room, str) else None
    room = room or None

    priority = data.get("priority")
    priority = priority.strip() if isinstance(priority, str) else None
    if priority not in allowed_priorities:
        priority = "NORMAL"

    summary = data.get("summary")
    summary = summary.strip() if isinstance(summary, str) and summary.strip() else ""

    missing_fields = normalize_missing_fields(data.get("missing_fields"))
    if not building or building not in allowed_buildings:
        building = None
        ensure_missing_field(missing_fields, "building")
    if not room:
        ensure_missing_field(missing_fields, "room")

    needs_human_review = bool(data.get("needs_human_review"))
    if not building or not room:
        needs_human_review = True

    return ExtractFieldsResponse(
        request_type=request_type,
        building=building,
        room=room,
        priority=priority or "NORMAL",
        summary=summary,
        missing_fields=normalize_missing_fields(missing_fields),
        needs_human_review=needs_human_review,
        confidence=clamp_confidence(data.get("confidence")),
    )


def validate_intake(
    request_type: str,
    confidence: Any,
    field_data: dict[str, Any],
    valid_buildings: list[str],
    valid_priorities: list[str],
) -> tuple[str, float, IntakeFields, IntakeValidation]:
    validated = validate_extracted_fields(
        {
            "request_type": request_type,
            "building": field_data.get("building"),
            "room": field_data.get("room"),
            "priority": field_data.get("priority"),
            "summary": field_data.get("summary"),
            "missing_fields": [],
            "needs_human_review": False,
            "confidence": confidence,
        },
        valid_buildings,
        valid_priorities,
    )
    errors: list[str] = []
    if validated.request_type == "Unknown":
        errors.append("request_type is Unknown")
    if not validated.building:
        errors.append("building is missing or invalid")
    if not validated.room:
        errors.append("room is missing")
    can_create_work_order = not errors
    return (
        validated.request_type,
        validated.confidence,
        IntakeFields(
            building=validated.building,
            room=validated.room,
            priority=validated.priority,
            summary=validated.summary,
        ),
        IntakeValidation(
            can_create_work_order=can_create_work_order,
            needs_human_review=not can_create_work_order,
            missing_fields=validated.missing_fields,
            errors=errors,
            warnings=[ADVISORY_WARNING],
        ),
    )


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


def issue_fields(items: Any) -> set[str]:
    fields: set[str] = set()
    if not isinstance(items, list):
        return fields
    for item in items:
        if isinstance(item, dict):
            value = item.get("field") or item.get("message") or ""
        else:
            value = str(item)
        fields.add(str(value).lower())
    return fields


def compare_test_case_result(expected_json: dict[str, Any] | None, actual_response: dict[str, Any]) -> dict[str, Any]:
    expected = expected_json or {}
    field_results = []
    passed = True
    for field in ["building", "room", "priority", "work_order_type", "assign_to", "issue_to", "job_type"]:
        if field not in expected:
            continue
        actual = extract_result_value(actual_response, field)
        ok = actual == expected.get(field)
        passed = passed and ok
        field_results.append({"field": field, "expected": expected.get(field), "actual": actual, "passed": ok})

    summary_results = []
    summary = str(extract_result_value(actual_response, "summary") or actual_response.get("summary") or "").lower()
    for needle in expected.get("summary_contains") or []:
        ok = str(needle).lower() in summary
        passed = passed and ok
        summary_results.append({"contains": needle, "passed": ok})

    contract_result = {}
    if "contract_valid" in expected:
        actual = actual_response.get("contract", {}).get("valid") if isinstance(actual_response.get("contract"), dict) else None
        ok = actual == expected["contract_valid"]
        passed = passed and ok
        contract_result = {"expected": expected["contract_valid"], "actual": actual, "passed": ok}

    environment_result = {}
    ai_validation = actual_response.get("ai_validation") if isinstance(actual_response.get("ai_validation"), dict) else {}
    if "environment_valid" in expected:
        actual = ai_validation.get("valid")
        ok = actual == expected["environment_valid"]
        passed = passed and ok
        environment_result["valid"] = {"expected": expected["environment_valid"], "actual": actual, "passed": ok}

    expected_errors = {str(value).lower() for value in expected.get("expected_errors") or []}
    expected_warnings = {str(value).lower() for value in expected.get("expected_warnings") or []}
    actual_error_fields = issue_fields(ai_validation.get("errors"))
    actual_warning_fields = issue_fields(ai_validation.get("warnings"))
    if expected_errors:
        ok = all(any(expected_field in actual_field for actual_field in actual_error_fields) for expected_field in expected_errors)
        passed = passed and ok
        environment_result["expected_errors"] = {"expected": sorted(expected_errors), "actual": sorted(actual_error_fields), "passed": ok}
    if expected_warnings:
        ok = all(any(expected_field in actual_field for actual_field in actual_warning_fields) for expected_field in expected_warnings)
        passed = passed and ok
        environment_result["expected_warnings"] = {"expected": sorted(expected_warnings), "actual": sorted(actual_warning_fields), "passed": ok}

    return {
        "passed": passed,
        "field_results": field_results,
        "summary_results": summary_results,
        "contract_result": contract_result,
        "environment_result": environment_result,
        "summary": "All assertions passed." if passed else "One or more assertions failed.",
    }


def test_case_run_status(comparison: dict[str, Any]) -> str:
    if comparison.get("passed"):
        return "passed"
    return "failed"


def prompt_version_label(prompt_id: int | None, endpoint: str) -> tuple[int | None, str | None]:
    row = prompt_row_for(endpoint, prompt_id)
    return row["id"], row["version"]


async def execute_ai_endpoint_for_test(
    endpoint: str,
    input_text: str,
    environment_code: str | None,
    source: str = "test_case",
    prompt_id: int | None = None,
) -> dict[str, Any]:
    if endpoint == "summarize-work-order":
        messages, meta = prompt_messages(endpoint, {"text": input_text}, prompt_id)
        summary = await call_ollama(messages, temperature=meta["temperature"], model=meta["model"])
        return {"summary": summary, "prompt": meta}
    if endpoint == "cmms-assistant":
        messages, meta = prompt_messages(endpoint, {"text": input_text}, prompt_id)
        response = await call_ollama(messages, temperature=meta["temperature"], model=meta["model"])
        return {
            "mode": "cmms-assistant",
            "response": response,
            "model": meta["model"],
            "prompt": meta,
            "safety": {"advisory_only": True, "cmms_write_back": False, "work_order_created": False, "email_sent": False},
        }
    if endpoint == "extract-work-order-fields":
        payload = ExtractFieldsRequest(text=input_text, environment_code=environment_code, source=source)
        valid_buildings, valid_priorities, _env_code = resolve_validation_lists(payload)
        messages, meta = prompt_messages(
            endpoint,
            {
                "text": input_text,
                "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
                "valid_buildings": valid_buildings,
                "valid_priorities": valid_priorities,
            },
            prompt_id,
        )
        content = await call_ollama(messages, temperature=meta["temperature"], model=meta["model"])
        result = validate_extracted_fields(parse_json_response(content), valid_buildings, valid_priorities).model_dump()
        result["prompt"] = meta
        return result
    if endpoint != "cmms-intake":
        raise HTTPException(status_code=400, detail="Unsupported test case endpoint")

    payload = ExtractFieldsRequest(text=input_text, environment_code=environment_code, source=source)
    env_hint = payload.environment_code.upper() if payload.environment_code else None
    run_id = start_workflow_run("cmms-intake", environment_code=env_hint, source=source)
    current_step: int | None = None
    try:
        current_step = start_workflow_step(run_id, "request_received", 10, input_summary=f"{redacted_summary(input_text)} | source={source} environment={env_hint or 'none'}")
        finish_workflow_step(current_step, "passed", output_summary="Test case request accepted")
        current_step = None

        valid_buildings, valid_priorities, env_code = resolve_validation_lists(payload)
        current_step = start_workflow_step(run_id, "model_extraction", 20, model=MODEL_NAME, prompt_version="pending", input_summary=f"text_length={len(input_text)}")
        intake_messages, meta = intake_prompt_messages(
            {
                "text": input_text,
                "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
                "valid_buildings": valid_buildings,
                "valid_priorities": valid_priorities,
            },
            prompt_id,
        )
        db_execute("UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?", (meta["model"], f"{meta['prompt_id']}:{meta['prompt_version']}", current_step))
        classifier_data = parse_json_response(await call_ollama(intake_messages["classifier"], temperature=meta["temperature"], model=meta["model"]))
        extractor_data = parse_json_response(await call_ollama(intake_messages["field_extractor"], temperature=meta["temperature"], model=meta["model"]))
        request_type, confidence, fields, validation = validate_intake(
            classifier_data.get("request_type"),
            classifier_data.get("confidence"),
            extractor_data,
            valid_buildings,
            valid_priorities,
        )
        draft_context = {"text": input_text, "request_type": request_type, "fields": fields.model_dump(), "validation": validation.model_dump()}
        draft_data = parse_json_response(await call_ollama([intake_messages["draft_generator"][0], {"role": "user", "content": json.dumps(draft_context)}], temperature=meta["temperature"], model=meta["model"]))
        finish_workflow_step(current_step, "passed", output_summary=f"type={request_type} confidence={confidence:.2f}", output_json={"request_type": request_type, "confidence": confidence, "model_call_count": 3, "prompt_id": meta["prompt_id"], "prompt_version": meta["prompt_version"], "temperature": meta["temperature"], "fields": fields.model_dump(), "missing_fields": validation.missing_fields})
        current_step = None

        result_payload = {"summary": fields.summary, "building": fields.building, "room": fields.room, "priority": fields.priority, "work_order_type": request_type, "assign_to": None, "issue_to": None, "job_type": None, "confidence": confidence}
        current_step = start_workflow_step(run_id, "output_contract_validation", 30, input_summary="endpoint=cmms-intake")
        contract_validation = validate_output_contract("cmms-intake", result_payload)
        finish_workflow_step(current_step, "passed" if contract_validation["valid"] else "failed", output_summary=f"contract_valid={contract_validation['valid']} errors={len(contract_validation['errors'])}", output_json={"contract_version": contract_validation["contract_version"], "valid": contract_validation["valid"], "error_count": len(contract_validation["errors"]), "warning_count": len(contract_validation["warnings"])})
        current_step = None
        contract_block = {"version": contract_validation["contract_version"], "valid": contract_validation["valid"], "errors": contract_validation["errors"], "warnings": contract_validation["warnings"]}

        current_step = start_workflow_step(run_id, "environment_validation", 40, input_summary=f"environment={env_code or 'none'}")
        if env_code and contract_validation["valid"]:
            ai_validation = validate_ai_output(env_code, contract_validation["normalized_payload"])
            ai_validation["enabled"] = True
            ai_validation["status"] = "completed"
            env_status = "failed" if ai_validation["valid"] is False else ("warning" if ai_validation.get("warnings") else "passed")
            finish_workflow_step(current_step, env_status, output_summary=f"validation_valid={ai_validation['valid']} warnings={len(ai_validation.get('warnings', []))} errors={len(ai_validation.get('errors', []))}", output_json={"valid": ai_validation["valid"], "error_count": len(ai_validation.get("errors", [])), "warning_count": len(ai_validation.get("warnings", [])), "normalized": ai_validation.get("normalized", {})})
        else:
            ai_validation = skipped_ai_validation() if env_code else {"enabled": False, "valid": None, "status": "not_run", "message": "No environment_code was supplied.", "errors": [], "warnings": [], "normalized": {}}
            finish_workflow_step(current_step, "skipped", output_summary="Skipped because output contract validation failed." if env_code else "Skipped because no environment_code was supplied.", output_json={"status": ai_validation.get("status"), "valid": ai_validation.get("valid")})
        current_step = None

        current_step = start_workflow_step(run_id, "response_composed", 50)
        drafts = IntakeDrafts(draft_wo_description=str(draft_data.get("draft_wo_description") or fields.summary), internal_note=str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."), client_reply=str(draft_data.get("client_reply") or "Thanks, we captured your request."))
        run_status = "failed" if not contract_validation["valid"] else ("completed_with_warnings" if ai_validation.get("warnings") else "completed")
        finish_workflow_step(current_step, "passed", output_summary=f"run_status={run_status}")
        finish_workflow_run(run_id, run_status)
        return IntakeResponse(run_id=run_id, endpoint="cmms-intake", environment_code=env_code, trace={"available": True, "run_id": run_id}, contract=contract_block, result=contract_validation["normalized_payload"] if contract_validation["valid"] else result_payload, ai_validation=ai_validation, raw={"included": False}, request_type=request_type, classification_confidence=confidence, fields=fields, validation=validation, drafts=drafts, model=meta["model"]).model_dump()
    except Exception as exc:
        if current_step is not None:
            fail_workflow_step(current_step, str(exc))
        finish_workflow_run(run_id, "failed", str(exc))
        raise


@app.on_event("startup")
async def startup() -> None:
    init_db()
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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, model=MODEL_NAME)


PORTAL_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CMMS LLM Management Portal</title>
  <style>
    :root {
      --azure: #0f62fe;
      --nav: #161616;
      --nav2: #262626;
      --bg: #f4f4f4;
      --panel: #fff;
      --line: #e0e0e0;
      --text: #161616;
      --muted: #525252;
      --danger: #da1e28;
      --ok: #24a148;
      --code: #0b0f19;
      --replicate-line: #e5e7eb;
      --accent: #635bff;
      --accent2: #2563eb;
      --accent-soft: #eef2ff;
      --surface: #ffffff;
      --surface-soft: #fafafa;
      --shadow-sm: 0 1px 2px rgba(16, 24, 40, .05);
      --shadow-md: 0 12px 28px rgba(16, 24, 40, .10);
      --radius: 14px;
      --radius-sm: 10px;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: var(--text); background: var(--bg); }
    .login { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #243642, #0f6cbd); }
    .login-card { width: min(420px, calc(100% - 32px)); background: #fff; border-radius: 2px; box-shadow: 0 18px 42px rgba(0,0,0,.28); padding: 28px; }
    .login-card h1 { margin: 0 0 8px; font-size: 24px; }
    .login-card p { margin: 0 0 22px; color: var(--muted); }
    label { display: block; font-size: 12px; font-weight: 650; margin: 12px 0 6px; color: #374151; }
    input, textarea, select {
      width: 100%; border: 1px solid #8a8886; border-radius: 2px; padding: 8px 10px; font: inherit; background: #fff;
    }
    textarea { min-height: 120px; resize: vertical; }
    button {
      border: 1px solid transparent; border-radius: 2px; padding: 8px 12px; background: var(--azure); color: #fff;
      font: inherit; font-weight: 600; cursor: pointer; min-height: 34px;
    }
    button.secondary { background: #fff; color: var(--text); border-color: #8a8886; }
    button.danger { background: var(--danger); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .app { display: none; min-height: 100vh; grid-template-columns: 260px 1fr; grid-template-rows: 48px 1fr; }
    .top { grid-column: 1 / -1; background: #161616; color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; border-bottom: 3px solid var(--azure); }
    .brand { font-weight: 700; font-size: 16px; }
    .userbar { display: flex; gap: 12px; align-items: center; font-size: 13px; }
    .nav { background: var(--nav); color: #fff; padding: 10px 0; overflow: auto; }
    .nav button { width: 100%; text-align: left; background: transparent; border: 0; border-left: 4px solid transparent; border-radius: 0; padding: 10px 18px; }
    .nav button.active { background: var(--nav2); border-left-color: #69afe5; }
    .nav button.admin-only::after { content: " admin"; color: #c8d1d8; font-size: 11px; float: right; }
    .content { padding: 18px; overflow: auto; }
    .page-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
    .page-title h1 { margin: 0; font-size: 24px; font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 0; }
    .card h2 { margin: 0; padding: 12px 14px; font-size: 16px; border-bottom: 1px solid var(--line); }
    .card-body { padding: 14px; }
    .span-3 { grid-column: span 3; } .span-4 { grid-column: span 4; } .span-6 { grid-column: span 6; } .span-8 { grid-column: span 8; } .span-12 { grid-column: span 12; }
    .metric { font-size: 28px; font-weight: 600; margin-bottom: 4px; }
    .muted { color: var(--muted); font-size: 13px; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .stack { display: grid; gap: 10px; }
    pre { margin: 0; background: var(--code); color: #f8fafc; padding: 14px; min-height: 260px; overflow: auto; white-space: pre-wrap; border-radius: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { background: #faf9f8; font-weight: 600; }
    .hidden { display: none !important; }
    .pill { display: inline-block; padding: 2px 7px; border-radius: 999px; background: #e1dfdd; font-size: 12px; }
    .pill.ok { background: #dff6dd; color: var(--ok); }
    .pill.danger { background: #fde7e9; color: var(--danger); }
    .pill.warning { background: #fff4ce; color: #8a6d00; }
    .segmented { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid #8a8886; border-radius: 2px; overflow: hidden; }
    .segmented button { border: 0; border-radius: 0; background: #fff; color: var(--text); }
    .segmented button.active { background: var(--azure); color: #fff; }
    .notice { border-left: 3px solid var(--azure); background: #f3f9fd; padding: 10px; font-size: 13px; }
    .notice.warning { border-left-color: #ffaa44; background: #fff8e1; }
    .voice-panel { border: 1px solid var(--line); background: #faf9f8; padding: 12px; }
    .status-line { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .button-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .playground { background: #fff; border: 1px solid var(--replicate-line); box-shadow: 0 1px 2px rgba(15,23,42,.04); }
    .playground h2 { border-bottom: 1px solid var(--replicate-line); }
    .playground-header { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 12px 14px; border-bottom: 1px solid var(--replicate-line); }
    .playground-title { font-weight: 700; }
    .playground-subtitle { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .run-surface { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; padding: 14px; }
    .ai-panel { border: 1px solid var(--replicate-line); background: #fff; padding: 12px; }
    .ai-panel-dark { background: #0b0f19; color: #f8fafc; border-color: #0b0f19; }
    .ai-panel-dark pre { min-height: 180px; padding: 0; background: transparent; }
    .result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .readiness { border-left: 3px solid var(--azure); background: #edf5ff; padding: 10px; }
    .readiness.fail { border-left-color: var(--danger); background: #fff1f1; }
    .readiness.warn { border-left-color: #f1c21b; background: #fcf4d6; }
    .code-output { min-height: 520px; }
    .contracts-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
    .detail-form input, .detail-form textarea, .detail-form select { width: 100%; min-width: 0; }
    .detail-form textarea { font-family: Consolas, "Courier New", monospace; }
    .command-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 10px; background: #fff; border: 1px solid var(--line); margin-bottom: 12px; }
    .command-bar select, .command-bar input { width: auto; min-width: 180px; }
    .resource-header { background: #fff; border: 1px solid var(--line); padding: 16px; margin-bottom: 12px; }
    .resource-title { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
    .tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin-bottom: 12px; }
    .tabs button { background: transparent; color: var(--text); border: 0; border-bottom: 3px solid transparent; border-radius: 0; }
    .tabs button.active { border-bottom-color: var(--azure); color: var(--azure); }
    .blade-layout { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 14px; }
    .blade { background: #fff; border: 1px solid var(--line); min-height: 420px; }
    .blade h2 { margin: 0; padding: 12px 14px; border-bottom: 1px solid var(--line); font-size: 16px; }
    .blade-body { padding: 14px; }
    .clickable-row { cursor: pointer; }
    .clickable-row:hover { background: #f3f9fd; }
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; z-index: 20; }
    .modal { width: min(760px, calc(100% - 32px)); background: #fff; border: 1px solid var(--line); box-shadow: 0 18px 42px rgba(0,0,0,.32); }
    .modal h2 { margin: 0; padding: 14px; border-bottom: 1px solid var(--line); font-size: 18px; }
    .modal-body { padding: 14px; }
    .modal-actions { padding: 12px 14px; border-top: 1px solid var(--line); display: flex; justify-content: flex-end; gap: 8px; }
    .preview-summary { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 12px 0; }
    .preview-summary div { background: #f8f8f8; border: 1px solid var(--line); padding: 10px; }

    /* Modern CMMS control layer: Linear/OpenAI-inspired admin controls with Replicate-style execution panels. */
    body { background: #f7f7f8; letter-spacing: 0; }
    input, textarea, select, .cmms-input, .cmms-select {
      min-height: 38px;
      border: 1px solid #d8dce3;
      border-radius: 10px;
      background: #fff;
      color: #111827;
      padding: 9px 12px;
      outline: none;
      transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
      box-shadow: 0 1px 0 rgba(17, 24, 39, .02);
    }
    textarea { min-height: 132px; line-height: 1.45; }
    input:hover, textarea:hover, select:hover { border-color: #c3c8d2; }
    input:focus, textarea:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 4px rgba(99, 91, 255, .13);
    }
    input:disabled, textarea:disabled, select:disabled {
      background: #f3f4f6;
      color: #6b7280;
      cursor: not-allowed;
    }
    select {
      appearance: none;
      background-image:
        linear-gradient(45deg, transparent 50%, #6b7280 50%),
        linear-gradient(135deg, #6b7280 50%, transparent 50%);
      background-position: calc(100% - 18px) 52%, calc(100% - 13px) 52%;
      background-size: 5px 5px, 5px 5px;
      background-repeat: no-repeat;
      padding-right: 34px;
    }
    input[type="checkbox"] {
      appearance: none;
      width: 18px !important;
      height: 18px;
      min-height: 18px;
      padding: 0;
      border-radius: 5px;
      vertical-align: -4px;
      margin-right: 8px;
      display: inline-grid;
      place-items: center;
    }
    input[type="checkbox"]:checked {
      background: var(--accent);
      border-color: var(--accent);
    }
    input[type="checkbox"]:checked::after {
      content: "";
      width: 9px;
      height: 5px;
      border: 2px solid #fff;
      border-top: 0;
      border-right: 0;
      transform: rotate(-45deg);
      margin-top: -2px;
    }
    button, .cmms-btn {
      min-height: 38px;
      border-radius: 10px;
      border: 1px solid transparent;
      padding: 8px 14px;
      background: linear-gradient(180deg, #6d66ff, #554cf2);
      color: #fff;
      box-shadow: 0 1px 2px rgba(17, 24, 39, .08);
      transition: transform .12s ease, box-shadow .16s ease, background .16s ease, border-color .16s ease;
    }
    button:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(85, 76, 242, .18); }
    button:active:not(:disabled) { transform: translateY(0); box-shadow: 0 1px 2px rgba(17, 24, 39, .08); }
    button.secondary, .cmms-btn.secondary {
      background: #fff;
      color: #111827;
      border-color: #d8dce3;
      box-shadow: var(--shadow-sm);
    }
    button.secondary:hover:not(:disabled) { border-color: #b9c0cc; box-shadow: 0 6px 14px rgba(17, 24, 39, .08); }
    button.danger, .cmms-btn.danger { background: #dc2626; color: #fff; }
    button:disabled { background: #eef0f4; color: #9ca3af; border-color: #e5e7eb; box-shadow: none; transform: none; }
    .login { background: radial-gradient(circle at 30% 20%, #eef2ff, transparent 32%), linear-gradient(135deg, #fbfbfc, #eef2ff); }
    .login-card {
      border-radius: 20px;
      border: 1px solid rgba(229, 231, 235, .9);
      box-shadow: var(--shadow-md);
      padding: 32px;
    }
    .login-card h1 { font-size: 26px; letter-spacing: -.01em; }
    .app { grid-template-columns: 190px 1fr; grid-template-rows: 52px 1fr; }
    .top {
      background: rgba(255, 255, 255, .88);
      color: #111827;
      border-bottom: 1px solid #e5e7eb;
      backdrop-filter: blur(12px);
    }
    .brand { font-size: 15px; letter-spacing: -.01em; }
    .userbar button.secondary { min-height: 32px; padding: 6px 11px; }
    .nav { background: #fff; color: #111827; border-right: 1px solid #e5e7eb; padding: 12px 8px; }
    .nav button {
      color: #374151;
      border: 0;
      border-radius: 10px;
      padding: 9px 11px;
      margin: 2px 0;
      display: flex;
      align-items: center;
      gap: 9px;
      font-weight: 620;
      font-size: 13px;
    }
    .nav button:hover { background: #f4f4f5; transform: none; box-shadow: none; }
    .nav button.active { background: var(--accent-soft); color: #3730a3; border-left-color: transparent; }
    .nav button.admin-only::after {
      content: "●";
      color: #ef4444;
      font-size: 11px;
      margin-left: auto;
      float: none;
    }
    .cmms-nav-icon { width: 18px; text-align: center; opacity: .82; }
    .content { padding: 22px; }
    .page-title h1 { font-size: 26px; letter-spacing: -.025em; }
    .card, .cmms-card, .playground, .blade, .modal, .resource-header {
      border-radius: var(--radius);
      border-color: #e5e7eb;
      box-shadow: var(--shadow-sm);
      overflow: hidden;
    }
    .card h2, .blade h2, .modal h2 {
      font-size: 15px;
      background: #fff;
      border-bottom-color: #eef0f3;
    }
    .ai-panel, .voice-panel, .readiness {
      border-radius: 14px;
      border-color: #e5e7eb;
      box-shadow: var(--shadow-sm);
    }
    .ai-panel-dark, .cmms-code-panel {
      border-radius: 14px;
      background: #0f172a;
      border-color: #111827;
      box-shadow: 0 12px 28px rgba(15, 23, 42, .16);
    }
    pre { border-radius: 12px; font-size: 12px; line-height: 1.5; }
    table { border-collapse: separate; border-spacing: 0; }
    th {
      background: #f9fafb;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: .02em;
      font-size: 11px;
      border-bottom: 1px solid #e5e7eb;
    }
    td { border-bottom-color: #eef0f3; }
    tr:hover td { background: #fafafa; }
    .pill, .cmms-badge {
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 11px;
      font-weight: 650;
      background: #f3f4f6;
      color: #4b5563;
    }
    .pill.ok { background: #ecfdf3; color: #027a48; }
    .pill.danger { background: #fef2f2; color: #b42318; }
    .pill.warning { background: #fffaeb; color: #b54708; }
    .segmented, .cmms-segmented {
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 3px;
      gap: 3px;
    }
    .segmented button {
      min-height: 32px;
      border-radius: 9px;
      background: transparent;
      color: #4b5563;
      box-shadow: none;
    }
    .segmented button.active {
      background: #fff;
      color: #111827;
      box-shadow: var(--shadow-sm);
    }
    .command-bar, .cmms-command-bar {
      border-radius: 14px;
      border-color: #e5e7eb;
      box-shadow: var(--shadow-sm);
      padding: 12px;
    }
    .command-bar select, .command-bar input { min-height: 36px; }
    .modal-backdrop { background: rgba(15, 23, 42, .35); backdrop-filter: blur(4px); }
    .modal { border-radius: 18px; box-shadow: var(--shadow-md); }
    .modal-actions { background: #fafafa; }
    .preview-summary div { border-radius: 12px; background: #fff; border-color: #e5e7eb; }
    @media (max-width: 1200px) { .contracts-layout { grid-template-columns: 1fr; } }
    @media (max-width: 900px) { .app { grid-template-columns: 1fr; } .nav { display: flex; overflow-x: auto; } .nav button { min-width: 180px; } .span-3,.span-4,.span-6,.span-8 { grid-column: span 12; } .result-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div id="loginView" class="login">
    <div class="login-card">
      <h1>CMMS LLM Portal</h1>
      <p>Sign in to manage environments, API keys, reports, and testing.</p>
      <label>Username</label><input id="loginUser" value="admin">
      <label>Password</label><input id="loginPass" type="password" placeholder="Enter admin password">
      <div class="row" style="margin-top:18px"><button onclick="login()">Sign in</button><span id="loginMsg" class="muted"></span></div>
    </div>
  </div>
  <div id="appView" class="app">
    <header class="top">
      <div class="brand">CMMS LLM Management Portal</div>
      <div class="userbar"><span id="healthText">Checking...</span><span id="userText"></span><button class="secondary" onclick="logout()">Logout</button></div>
    </header>
    <nav class="nav" id="nav"></nav>
    <main class="content">
      <div class="page-title"><h1 id="pageTitle">Dashboard</h1><div id="pageActions"></div></div>
      <div id="page"></div>
    </main>
  </div>
  <script>
    const state = {
      me: null, page: "dashboard", envs: [], keys: [], output: {}, selectedEnv: "DEFAULT", defaultApiKey: "my-secret-key",
      envTab: "codes", selectedCategory: "buildings", selectedCode: null, codeData: null, validationRules: [],
      inputMode: "text", recognition: null, voiceSupported: null, voiceBaseTranscript: "", voiceFinalTranscript: "",
      voiceStopping: false, voiceStatus: "Idle", voiceSilenceTimer: null, outputs: {},
      lastTestResponse: null, lastTestInput: null, selectedTestCaseId: null
    };
    const menu = [
      ["dashboard","Dashboard",false,"▦"],["test","Test Console",false,"▶"],["builder","API Builder",false,"⌘"],["testCases","Test Cases",true,"✓"],["testSuites","Test Suites",true,"✓"],
      ["environments","Environments",true,"◇"],["contracts","Output Contracts",true,"▣"],["prompts","Prompt Versions",true,"✎"],["keys","API Keys",true,"◆"],
      ["users","Users",true,"◉"],["logs","Logs",false,"☰"],["reports","Reports",false,"↗"],["kb","Knowledge Base",false,"◌"],
      ["remote","Remote Access",true,"⇄"],["system","System",true,"⚙"]
    ];
    const codeCategories = [
      ["buildings","Buildings"],["rooms","Rooms"],["priorities","Priorities"],["work_order_types","Work order types"],
      ["assign_to","Assign to"],["issue_to_employee_number","Issue to employee #"],["job_type","Job type"],["custom:future","Custom future"]
    ];
    const $ = (id) => document.getElementById(id);
    async function api(path, opts = {}) {
      const res = await fetch(path, { credentials: "same-origin", ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
      if (!res.ok) throw Object.assign(new Error(data.detail || "Request failed"), { data, status: res.status });
      return data;
    }
    async function login() {
      try {
        await api("/auth/login", { method: "POST", body: JSON.stringify({ username: $("loginUser").value, password: $("loginPass").value }) });
        await boot();
      } catch (e) { $("loginMsg").textContent = e.message; }
    }
    async function logout() { await api("/auth/logout", { method: "POST" }).catch(() => {}); location.reload(); }
    async function boot() {
      try {
        state.me = await api("/api/me");
        $("loginView").style.display = "none"; $("appView").style.display = "grid";
        $("userText").textContent = `${state.me.username} (${state.me.role})`;
        renderNav(); await refreshBase(); show("dashboard");
      } catch { $("loginView").style.display = "grid"; $("appView").style.display = "none"; }
    }
    async function refreshBase() {
      state.envs = await api("/api/environments").catch(() => []);
      state.keys = state.me?.role === "admin" ? await api("/api/admin/api-keys").catch(() => []) : [];
      const keyInfo = await api("/api/default-api-key").catch(() => null);
      if (keyInfo?.api_key) state.defaultApiKey = keyInfo.api_key;
      const health = await api("/health").catch(() => null);
      $("healthText").textContent = health ? "Local API online" : "API offline";
    }
    function renderNav() {
      $("nav").innerHTML = menu.map(([id,label,admin,icon]) => {
        if (admin && state.me.role !== "admin") return "";
        return `<button class="${state.page===id?'active':''} ${admin?'admin-only':''}" onclick="show('${id}')"><span class="cmms-nav-icon">${icon}</span><span>${label}</span></button>`;
      }).join("");
    }
    function pageShell(title, html) { $("pageTitle").textContent = title; $("pageActions").innerHTML = ""; $("page").innerHTML = html; renderNav(); }
    function envOptions() { return state.envs.map(e => `<option value="${e.environment_code}">${e.environment_code} - ${e.name}</option>`).join(""); }
    function show(id) {
      state.page = id; renderNav();
      const handlers = { dashboard, test, builder, testCases, testSuites, environments, contracts, prompts, keys, users, logs, reports, kb, remote, system };
      handlers[id]();
    }
    async function dashboard() {
      pageShell("Dashboard", `<div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${state.envs.length}</div><div class="muted">Environments</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${state.keys.length}</div><div class="muted">API keys</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${state.me.role}</div><div class="muted">Current role</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">Local</div><div class="muted">Model runtime</div></div></div>
        <div class="card span-12"><h2>Safety posture</h2><div class="card-body">Advisory mode only. No CMMS write-back, work order creation, approval, or email sending occurs.</div></div>
        <div class="card span-12"><h2>Regression Health</h2><div class="card-body" id="regressionDashboard"><p class="muted">Loading regression dashboard...</p></div></div>
      </div>`);
      const data = await api("/api/admin/regression-dashboard").catch(e => ({ error: e.message }));
      renderRegressionDashboard(data);
    }

    function renderRegressionDashboard(data) {
      if (!$("regressionDashboard")) return;
      if (data.error) { $("regressionDashboard").innerHTML = `<span class="pill danger">Dashboard unavailable</span><p>${escapeHtml(data.error)}</p>`; return; }
      const readiness = data.required_suite_readiness || {};
      const workflow = data.workflow_summary || {};
      $("regressionDashboard").innerHTML = `<div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.passed ?? 0}/${readiness.total ?? 0}</div><div class="muted">Required suites passed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.failed ?? 0}</div><div class="muted">Required suites failed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.not_run ?? 0}</div><div class="muted">Required suites not run</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${workflow.failed ?? 0}</div><div class="muted">Recent workflow failures</div></div></div>
        <div class="card span-12"><h2>Required Suite Readiness</h2><div class="card-body">${renderRequiredSuiteReadiness(readiness.items || [])}</div></div>
        <div class="card span-12"><h2>Latest Suite Runs</h2><div class="card-body">${renderDashboardSuiteRuns(data.latest_suite_runs || [])}</div></div>
        <div class="card span-6"><h2>Recent Prompt Comparisons</h2><div class="card-body">${renderDashboardComparisons(data.recent_prompt_comparisons || [])}</div></div>
        <div class="card span-6"><h2>Recent Promotions</h2><div class="card-body">${renderDashboardPromotions(data.recent_promotions || [])}</div></div>
        <div class="card span-4"><h2>Workflow Summary</h2><div class="card-body">${renderWorkflowSummary(workflow)}</div></div>
        <div class="card span-4"><h2>Top Failing Fields</h2><div class="card-body">${renderFailingFields(data.top_failing_fields || [])}</div></div>
        <div class="card span-4"><h2>Recent Validation Failures</h2><div class="card-body">${renderValidationFailures(data.recent_validation_failures || [])}</div></div>
      </div>`;
    }

    function statusPill(status) {
      return `<span class="pill ${status === "passed" || status === "completed" ? "ok" : status === "warning" || status === "completed_with_warnings" || status === "not_run" ? "warning" : "danger"}">${escapeHtml(status || "")}</span>`;
    }

    function renderRequiredSuiteReadiness(rows) {
      if (!rows.length) return '<p class="muted">No required suites configured.</p>';
      return `<table><thead><tr><th>Suite</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Pass Rate</th><th>Status</th><th>Last Run</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.latest_prompt_version || "")}</td><td>${r.pass_rate ?? ""}</td><td>${statusPill(r.status)}</td><td>${escapeHtml(r.last_run_at || "")}</td><td>${r.latest_suite_run_id ? `<button class="secondary" onclick="viewTestSuiteRun('${escapeAttr(r.latest_suite_run_id)}')">View Suite Run</button>` : ""}</td></tr>`).join("")}</tbody></table>`;
    }

    function renderDashboardSuiteRuns(rows) {
      if (!rows.length) return '<p class="muted">No suite runs yet.</p>';
      return `<table><thead><tr><th>Run</th><th>Suite</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Status</th><th>Pass Rate</th><th>Started</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.suite_run_id)}</td><td>${escapeHtml(r.suite_name || "")}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.prompt_version || "")}</td><td>${statusPill(r.status)}</td><td>${r.pass_rate ?? ""}</td><td>${escapeHtml(r.started_at || "")}</td><td><button class="secondary" onclick="viewTestSuiteRun('${escapeAttr(r.suite_run_id)}')">View</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderDashboardComparisons(rows) {
      if (!rows.length) return '<p class="muted">No prompt comparisons yet.</p>';
      return `<table><thead><tr><th>Comparison</th><th>Endpoint</th><th>Improved</th><th>Regressed</th><th>Error</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.comparison_id)}</td><td>${escapeHtml(r.endpoint)}</td><td>${r.improved}</td><td>${r.regressed}</td><td>${r.error}</td><td><button class="secondary" onclick="show('prompts'); setTimeout(()=>viewPromptComparison('${escapeAttr(r.comparison_id)}'), 100)">View</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderDashboardPromotions(rows) {
      if (!rows.length) return '<p class="muted">No prompt promotions yet.</p>';
      return `<table><thead><tr><th>Promotion</th><th>Endpoint</th><th>Promoted</th><th>Gate</th><th>Override</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.promotion_id)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.promoted_prompt || "")}</td><td>${statusPill(r.gate_status)}</td><td>${r.override_used ? "Yes" : "No"}</td><td><button class="secondary" onclick="viewPromptPromotion('${escapeAttr(r.promotion_id)}')">View</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderWorkflowSummary(w) {
      return `<div class="stack"><div>Total: <strong>${w.total ?? 0}</strong></div><div>Completed: <strong>${w.completed ?? 0}</strong></div><div>Warnings: <strong>${w.completed_with_warnings ?? 0}</strong></div><div>Failed: <strong>${w.failed ?? 0}</strong></div><div>Avg duration: <strong>${w.avg_duration_ms ?? 0} ms</strong></div></div>`;
    }

    function renderFailingFields(rows) {
      if (!rows.length) return '<p class="muted">No failing fields found.</p>';
      return `<table><thead><tr><th>Field</th><th>Count</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.field)}</td><td>${r.count}</td></tr>`).join("")}</tbody></table>`;
    }

    function renderValidationFailures(rows) {
      if (!rows.length) return '<p class="muted">No recent validation failures.</p>';
      return `<table><thead><tr><th>When</th><th>Source</th><th>Field</th><th>Message</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.timestamp || "")}</td><td>${escapeHtml(r.source_type)}</td><td>${escapeHtml(r.field || "")}</td><td>${escapeHtml(r.message || "")}</td></tr>`).join("")}</tbody></table>`;
    }
    function test() {
      pageShell("Test Console", `<div class="grid">
        <div class="card playground span-4"><div class="playground-header"><div><div class="playground-title">Run console</div><div class="playground-subtitle">Text and voice share one editable input.</div></div><span class="pill">API</span></div><div class="card-body stack">
          <label>API key</label><input id="tKey" type="password" value="${escapeAttr(state.defaultApiKey)}">
          <label>Mode</label><select id="tEndpoint" onchange="renderTestModeHelp()"><option value="cmms-intake">CMMS Intake</option><option value="cmms-assistant">CMMS Assistant Chat</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select>
          <label>Environment</label><select id="tEnv">${envOptions()}</select>
          <div id="testModeHelp" class="notice"></div>
          <div id="testInputPanel"></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Response</div><div class="playground-subtitle" id="inputSourceLabel">Input source: none</div></div><span id="runStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="tReadiness" class="readiness"><strong>Work order readiness</strong><div class="muted">Run CMMS Intake to evaluate whether enough validated information exists for a human-controlled workflow.</div></div>
            <div class="ai-panel"><h3>Workflow Trace</h3><div id="tTrace"><span class="muted">Run CMMS Intake to see trace steps.</span></div></div>
            <div class="result-grid">
              <div class="ai-panel"><h3>Contract Validation</h3><div id="tContract"><span class="muted">Run a request to see contract validation.</span></div></div>
              <div class="ai-panel"><h3>Environment Validation</h3><div id="tValidation"><span class="muted">Run a request to see environment validation.</span></div></div>
            </div>
            <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Extracted JSON</strong>${outputToolbar("tOut")}</div><pre id="tOut">{}</pre></div>
          </div>
        </div>
      </div>`);
      renderTestInputPanel();
      renderTestModeHelp();
    }
    function renderTestInputPanel() {
      if (!$("testInputPanel")) return;
      const supported = getSpeechRecognitionCtor();
      state.voiceSupported = Boolean(supported);
      $("testInputPanel").innerHTML = `<div class="ai-panel stack">
          <label>Text / voice transcript</label>
          <textarea id="tText">The air conditioner in ARC room 205 is making loud noise and the room is too warm.</textarea>
          <div class="button-grid"><button id="runTestBtn" onclick="runTest('text')">Run</button><button class="secondary" onclick="clearVoiceTranscript()">Clear</button><button class="secondary" onclick="openSaveCurrentTestCase()">Save as Test Case</button><button class="secondary" onclick="runMatchingTestCase()">Run Matching Test</button></div>
        </div>
        <div class="voice-panel stack">
          <div class="status-line"><strong>Speech provider: Browser Speech Recognition</strong><span id="voiceStatus" class="pill">${escapeHtml(state.voiceStatus || "Idle")}</span></div>
          ${supported ? "" : '<div class="notice warning">Speech recognition is not available in this browser. Use Chrome, Edge, or Safari, or continue with text input.</div>'}
          <label>Language</label><select id="voiceLang" onchange="updateVoiceLanguage()">
            <option value="en-CA">English - Canada</option>
            <option value="en-US">English - US</option>
            <option value="zh-CN">Chinese - Simplified Mandarin</option>
            <option value="zh-TW">Chinese - Traditional Mandarin</option>
            <option value="fr-CA">French - Canada</option>
            <option value="es-ES">Spanish - Spain</option>
            <option value="ja-JP">Japanese</option>
            <option value="ko-KR">Korean</option>
          </select>
          <div class="button-grid">
            <button onclick="startVoiceRecognition()" ${supported ? "" : "disabled"}>Start Listening</button>
            <button class="secondary" onclick="stopVoiceRecognition()" ${supported ? "" : "disabled"}>Stop</button>
          </div>
          <div class="muted">Listening stops automatically after 5 seconds without detected speech.</div>
          <div id="voiceMessage" class="muted">Speech recognition is handled by the browser. This app does not store audio. Review the transcript before sending.</div>
        </div>`;
    }
    async function renderTestModeHelp() {
      if (!$("testModeHelp")) return;
      const ep = $("tEndpoint")?.value || "cmms-intake";
      const copy = {
        "cmms-intake": "Controlled extraction workflow: contract validation, environment validation, readiness, and advisory drafts.",
        "cmms-assistant": "Controlled CMMS assistant chat. It can discuss intake, validation, API usage, and drafts, but cannot create work orders or write to CMMS.",
        "extract-work-order-fields": "Field extraction only. Useful for debugging request type, building, room, priority, and missing fields.",
        "summarize-work-order": "One-sentence work request summary. No readiness validation."
      };
      $("testModeHelp").textContent = copy[ep] || copy["cmms-intake"];
      const promptInfo = await api(`/api/prompt-versions/active/${ep}`).catch(() => null);
      if (promptInfo) {
        $("testModeHelp").innerHTML = `${escapeHtml(copy[ep] || copy["cmms-intake"])}<div class="muted" style="margin-top:6px">Prompt Version: <strong>${escapeHtml(promptInfo.endpoint)} ${escapeHtml(promptInfo.version)}</strong> · temperature ${promptInfo.temperature}</div>`;
      }
    }
    function getSpeechRecognitionCtor() { return window.SpeechRecognition || window.webkitSpeechRecognition; }
    function updateVoiceLanguage() {
      if (state.recognition && $("voiceLang")) state.recognition.lang = $("voiceLang").value;
    }
    function setVoiceStatus(status, message) {
      state.voiceStatus = status;
      if ($("voiceStatus")) {
        $("voiceStatus").textContent = status;
        $("voiceStatus").className = `pill ${status === "Error" ? "danger" : status === "Listening" ? "ok" : status === "Processing" ? "warning" : ""}`;
      }
      if (message && $("voiceMessage")) $("voiceMessage").textContent = message;
    }
    function transcriptValue() {
      return ($("tText")?.value || "").trim();
    }
    function writeTranscript(interimText = "") {
      const parts = [state.voiceBaseTranscript, state.voiceFinalTranscript, interimText].map(v => (v || "").trim()).filter(Boolean);
      if ($("tText")) $("tText").value = parts.join(" ");
    }
    function startVoiceRecognition() {
      const SpeechRecognitionCtor = getSpeechRecognitionCtor();
      if (!SpeechRecognitionCtor) {
        setVoiceStatus("Error", "Speech recognition is not available in this browser. Use Chrome, Edge, or Safari, or continue with text input.");
        return;
      }
      if (state.recognition) {
        setVoiceStatus("Listening", "Speech recognition is already running.");
        return;
      }
      state.voiceBaseTranscript = transcriptValue();
      state.voiceFinalTranscript = "";
      state.voiceStopping = false;
      const recognition = new SpeechRecognitionCtor();
      state.recognition = recognition;
      recognition.lang = $("voiceLang")?.value || "en-CA";
      recognition.interimResults = true;
      try { recognition.continuous = true; } catch {}
      recognition.onstart = () => { setVoiceStatus("Listening", "Listening. The transcript will appear in the text box."); resetVoiceSilenceTimer(); };
      recognition.onerror = (event) => {
        const messages = {
          "not-allowed": "Microphone permission was denied. Allow microphone access or continue with text input.",
          "service-not-allowed": "Speech recognition service is blocked in this browser.",
          "no-speech": "No speech was detected. Try again or type the request.",
          "audio-capture": "No microphone was found or it could not be used.",
          "network": "Speech recognition network error. Try again or continue with text input."
        };
        setVoiceStatus("Error", messages[event.error] || `Speech recognition error: ${event.error || "unknown"}.`);
      };
      recognition.onresult = (event) => {
        setVoiceStatus("Processing");
        let finalChunk = "";
        let interimChunk = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const text = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalChunk += `${text} `;
          else interimChunk += text;
        }
        if (finalChunk.trim()) state.voiceFinalTranscript = `${state.voiceFinalTranscript} ${finalChunk}`.trim();
        writeTranscript(interimChunk);
        resetVoiceSilenceTimer();
        setVoiceStatus("Listening");
      };
      recognition.onend = () => {
        clearVoiceSilenceTimer();
        state.recognition = null;
        const endedWithError = state.voiceStatus === "Error";
        if (!endedWithError) setVoiceStatus("Idle", state.voiceStopping ? "Listening stopped. Review the transcript before sending." : "Speech recognition ended. Review the transcript before sending.");
      };
      try { recognition.start(); } catch (e) { setVoiceStatus("Error", e.message || "Could not start speech recognition."); }
    }
    function stopVoiceRecognition() {
      state.voiceStopping = true;
      if (state.recognition) {
        setVoiceStatus("Processing", "Stopping speech recognition...");
        try { state.recognition.stop(); } catch { state.recognition = null; setVoiceStatus("Idle"); }
      } else {
        setVoiceStatus("Idle", "Speech recognition is not running.");
      }
    }

    function clearVoiceSilenceTimer() {
      if (state.voiceSilenceTimer) {
        clearTimeout(state.voiceSilenceTimer);
        state.voiceSilenceTimer = null;
      }
    }

    function resetVoiceSilenceTimer() {
      clearVoiceSilenceTimer();
      state.voiceSilenceTimer = setTimeout(() => {
        if (state.recognition) {
          state.voiceStopping = true;
          setVoiceStatus("Processing", "Stopped automatically after 5 seconds without detected speech.");
          try { state.recognition.stop(); } catch {}
        }
      }, 5000);
    }
    function clearVoiceTranscript() {
      state.voiceBaseTranscript = "";
      state.voiceFinalTranscript = "";
      if ($("tText")) $("tText").value = "";
      setVoiceStatus("Idle", "Transcript cleared.");
    }
    function setVoiceSample(lang) {
      const samples = {
        en: "There is a water leak in ARC room 205. It looks urgent.",
        zh: "ARC 205 \u623f\u95f4\u6709\u6f0f\u6c34\u95ee\u9898\uff0c\u6bd4\u8f83\u7d27\u6025\u3002",
        fr: "Il y a une fuite d'eau dans la salle ARC 205. C'est urgent."
      };
      if ($("tText")) $("tText").value = samples[lang] || samples.en;
      state.voiceBaseTranscript = transcriptValue();
      state.voiceFinalTranscript = "";
      setVoiceStatus("Idle", "Sample transcript loaded. Review it before sending.");
    }
    async function runTest(sourceOverride) {
      const ep = $("tEndpoint").value;
      const source = sourceOverride || "text";
      const text = transcriptValue();
      if (!text) {
        const message = source === "voice_transcript" ? "Transcript is empty. Speak, type, or choose a sample before sending." : "Text is required.";
        if (source === "voice_transcript") setVoiceStatus("Error", message);
        setConsoleOutput("tOut", { error: message });
        return;
      }
      const body = { text, environment_code: $("tEnv").value };
      if (source === "voice_transcript") body.source = "voice_transcript";
      try {
        setRunLoading(true);
        const data = await api(`/api/ai/${ep}`, { method: "POST", headers: { "x-api-key": $("tKey").value }, body: JSON.stringify(body) });
        if ($("inputSourceLabel")) $("inputSourceLabel").textContent = source === "voice_transcript" ? "Input source: voice transcript" : "Input source: text";
        if ($("runStatus")) $("runStatus").textContent = "Complete";
        setConsoleOutput("tOut", data);
        state.lastTestResponse = data;
        state.lastTestInput = { endpoint: ep, environment_code: $("tEnv").value, text, source };
        renderContractValidation(data.contract);
        renderTestValidation(data.ai_validation);
        renderReadiness(data);
        renderWorkflowTraceFromResponse(data, "tTrace");
        if (source === "voice_transcript") setVoiceStatus("Idle", "Voice transcript sent to the API.");
      } catch (e) {
        if ($("runStatus")) $("runStatus").textContent = "Error";
        if (source === "voice_transcript") setVoiceStatus("Error", e.message || "API call failed.");
        setConsoleOutput("tOut", e.data || { error: e.message });
      } finally {
        setRunLoading(false);
      }
    }

    function setRunLoading(isLoading) {
      if ($("runStatus")) {
        $("runStatus").textContent = isLoading ? "Running..." : ($("runStatus").textContent === "Running..." ? "Ready" : $("runStatus").textContent);
        $("runStatus").className = `pill ${isLoading ? "warning" : ""}`;
      }
      if ($("runTestBtn")) {
        $("runTestBtn").disabled = isLoading;
        $("runTestBtn").textContent = isLoading ? "Running..." : "Run";
      }
    }

    function renderReadiness(data) {
      if (!$("tReadiness")) return;
      const summary = readinessSummary(data);
      $("tReadiness").className = `readiness ${summary.cls}`;
      $("tReadiness").innerHTML = summary.html;
    }

    function readinessSummary(data) {
      if (data.mode === "cmms-assistant") {
        return {
          cls: "warn",
          label: "Assistant chat response",
          html: '<strong>Assistant chat response</strong><div class="muted">Controlled advisory conversation only. No work order readiness decision, CMMS write-back, work order creation, or email sending.</div>'
        };
      }
      const validation = data.ai_validation;
      const legacy = data.validation;
      const contractOk = data.contract ? data.contract.valid : null;
      const envOk = validation ? validation.valid : null;
      const canCreate = legacy ? legacy.can_create_work_order : (contractOk === true && envOk === true);
      const missing = legacy?.missing_fields || [];
      const cls = canCreate ? "" : (envOk === false || contractOk === false ? "fail" : "warn");
      const label = canCreate ? "Ready for human-controlled workflow" : "Not ready for work order generation";
      return {
        cls,
        label,
        html: `<strong>${label}</strong><div class="muted">Advisory only. No work order was created.</div>
          <div style="margin-top:8px">Contract: <strong>${contractOk === null ? "n/a" : contractOk ? "passed" : "failed"}</strong> &nbsp; Environment: <strong>${envOk === null ? "n/a" : envOk ? "passed" : "failed"}</strong> &nbsp; Missing: <strong>${missing.length ? missing.join(", ") : "none"}</strong></div>`
      };
    }

    function renderContractValidation(contract) {
      if (!contract) { $("tContract").innerHTML = '<span class="muted">No output contract returned for this endpoint.</span>'; return; }
      const cls = contract.valid ? "ok" : "danger";
      $("tContract").innerHTML = `<div class="pill ${cls}">${contract.valid ? "Passed" : "Failed"}</div><span class="muted"> version ${escapeHtml(contract.version || "none")}</span>
        <h3>Errors</h3>${contract.errors?.length ? `<ul>${contract.errors.map(e=>`<li>${escapeHtml(e)}</li>`).join("")}</ul>` : '<p class="muted">None</p>'}
        <h3>Warnings</h3>${contract.warnings?.length ? `<ul>${contract.warnings.map(e=>`<li>${escapeHtml(e)}</li>`).join("")}</ul>` : '<p class="muted">None</p>'}`;
    }

    function renderTestValidation(validation) {
      if (!validation) { $("tValidation").innerHTML = '<span class="muted">No environment validation returned for this endpoint.</span>'; return; }
      const status = validation.valid ? (validation.warnings?.length ? "Passed with warnings" : "Passed") : "Failed";
      const cls = validation.valid ? "ok" : "danger";
      $("tValidation").innerHTML = `<div class="pill ${cls}">${status}</div>
        <h3>Errors</h3>${issueList(validation.errors)}
        <h3>Warnings</h3>${issueList(validation.warnings)}
        <h3>Normalized</h3><pre style="min-height:100px">${JSON.stringify(validation.normalized || {}, null, 2)}</pre>`;
    }

    async function renderWorkflowTraceFromResponse(data, targetId) {
      if (!$(targetId)) return;
      if (!data?.trace?.available || !data.trace.run_id) {
        $(targetId).innerHTML = '<span class="muted">No workflow trace for this response.</span>';
        return;
      }
      try {
        const trace = await api(`/api/admin/workflow-runs/${data.trace.run_id}`);
        $(targetId).innerHTML = renderWorkflowTrace(trace);
      } catch (e) {
        $(targetId).innerHTML = `<span class="muted">Trace ${escapeHtml(data.trace.run_id)} is available for admin users.</span>`;
      }
    }

    function renderWorkflowTrace(trace) {
      const icon = { passed: "✓", warning: "⚠", failed: "✕", skipped: "↷", running: "…" };
      const rows = (trace.steps || []).map(step => {
        const model = step.model ? ` — ${escapeHtml(step.model)}` : "";
        const prompt = step.prompt_version ? ` — ${escapeHtml(step.prompt_version)}` : "";
        const duration = step.duration_ms !== null && step.duration_ms !== undefined ? ` — ${step.duration_ms} ms` : "";
        const summary = step.output_summary || step.error_message || "";
        return `<div class="status-line" style="align-items:flex-start;border-bottom:1px solid #eef0f3;padding:8px 0">
          <div><strong>${icon[step.status] || "•"} ${escapeHtml(step.step_name.replaceAll("_", " "))}</strong><span class="muted">${model}${prompt}${duration}</span>${summary ? `<div class="muted">${escapeHtml(summary)}</div>` : ""}</div>
          <span class="pill ${step.status === "failed" ? "danger" : step.status === "warning" ? "warning" : step.status === "passed" ? "ok" : ""}">${escapeHtml(step.status)}</span>
        </div>`;
      }).join("");
      return `<div class="status-line"><strong>${escapeHtml(trace.run_id)}</strong><span class="pill ${trace.status === "failed" ? "danger" : trace.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(trace.status)}</span></div>${rows || '<p class="muted">No steps recorded.</p>'}`;
    }

    function renderWorkflowTrace(trace) {
      const icon = { passed: "OK", warning: "WARN", failed: "FAIL", skipped: "SKIP", running: "RUN" };
      const rows = (trace.steps || []).map(step => {
        const model = step.model ? ` - ${escapeHtml(step.model)}` : "";
        const prompt = step.prompt_version ? ` - ${escapeHtml(step.prompt_version)}` : "";
        const duration = step.duration_ms !== null && step.duration_ms !== undefined ? ` - ${step.duration_ms} ms` : "";
        const summary = step.output_summary || step.error_message || "";
        return `<div class="status-line" style="align-items:flex-start;border-bottom:1px solid #eef0f3;padding:8px 0">
          <div><strong>${icon[step.status] || "STEP"} ${escapeHtml(step.step_name.replaceAll("_", " "))}</strong><span class="muted">${model}${prompt}${duration}</span>${summary ? `<div class="muted">${escapeHtml(summary)}</div>` : ""}</div>
          <span class="pill ${step.status === "failed" ? "danger" : step.status === "warning" ? "warning" : step.status === "passed" ? "ok" : ""}">${escapeHtml(step.status)}</span>
        </div>`;
      }).join("");
      return `<div class="status-line"><strong>${escapeHtml(trace.run_id)}</strong><span class="pill ${trace.status === "failed" ? "danger" : trace.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(trace.status)}</span></div>
        <div class="row" style="margin:10px 0"><button class="secondary" onclick="createTestCaseFromTrace('${escapeAttr(trace.run_id)}')">Create Test Case from Run</button><button class="secondary" onclick="replayWorkflowRun('${escapeAttr(trace.run_id)}')">Replay Run</button></div>
        ${rows || '<p class="muted">No steps recorded.</p>'}`;
    }

    function issueList(items) {
      if (!items || !items.length) return '<p class="muted">None</p>';
      return `<ul>${items.map(i=>`<li><strong>${escapeHtml(i.field)}</strong>: ${escapeHtml(i.message)} <span class="muted">(${escapeHtml(i.value ?? "")})</span></li>`).join("")}</ul>`;
    }

    function outputToolbar(id) {
      return `<span class="row" style="gap:6px"><label style="margin:0;color:inherit"><input id="${id}Pretty" type="checkbox" checked onchange="refreshConsoleOutput('${id}')"> Pretty</label><button class="secondary" onclick="copyConsoleOutput('${id}')">Copy</button><button class="secondary" onclick="downloadConsoleOutput('${id}')">Download</button></span>`;
    }

    function setConsoleOutput(id, value, isJson = true) {
      state.outputs[id] = { value, isJson };
      refreshConsoleOutput(id);
    }

    function formatConsoleOutput(id) {
      const output = state.outputs[id];
      if (!output) return $(id)?.textContent || "";
      if (!output.isJson) return String(output.value ?? "");
      const pretty = $(`${id}Pretty`)?.checked !== false;
      return pretty ? JSON.stringify(output.value, null, 2) : JSON.stringify(output.value);
    }

    function refreshConsoleOutput(id) {
      if ($(id)) $(id).textContent = formatConsoleOutput(id);
    }

    async function copyConsoleOutput(id) {
      const text = formatConsoleOutput(id);
      await navigator.clipboard?.writeText(text);
    }

    function downloadConsoleOutput(id) {
      const text = formatConsoleOutput(id);
      const blob = new Blob([text], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${id}-${new Date().toISOString().replaceAll(":", "-")}.txt`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }

    function expectedFromResponse(response) {
      if (!response) return {};
      return {
        summary_contains: response.result?.summary ? [String(response.result.summary).slice(0, 40)] : [],
        building: response.result?.building ?? response.fields?.building ?? null,
        room: response.result?.room ?? response.fields?.room ?? null,
        priority: response.result?.priority ?? response.fields?.priority ?? null,
        work_order_type: response.result?.work_order_type ?? response.request_type ?? null,
        contract_valid: response.contract?.valid ?? null,
        environment_valid: response.ai_validation?.valid ?? null,
        expected_errors: [],
        expected_warnings: []
      };
    }

    function openSaveCurrentTestCase() {
      const current = state.lastTestInput || { endpoint: $("tEndpoint")?.value, environment_code: $("tEnv")?.value, text: $("tText")?.value, source: "manual" };
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="saveTestCaseModal"><div class="modal"><h2>Save Test Case</h2><div class="modal-body stack">
        <label>Name</label><input id="saveTcName" value="${escapeAttr((current.text || "CMMS request").slice(0, 60))}">
        <label>Endpoint</label><input id="saveTcEndpoint" value="${escapeAttr(current.endpoint || "cmms-intake")}">
        <label>Environment</label><input id="saveTcEnv" value="${escapeAttr(current.environment_code || "")}">
        <label>Input text</label><textarea id="saveTcText">${escapeHtml(current.text || "")}</textarea>
        <label>Expected JSON</label><textarea id="saveTcExpected" style="min-height:220px">${escapeHtml(JSON.stringify(expectedFromResponse(state.lastTestResponse), null, 2))}</textarea>
        <label>Tags</label><input id="saveTcTags" value="console">
        <label>Notes</label><textarea id="saveTcNotes"></textarea>
      </div><div class="modal-actions"><button class="secondary" onclick="closeSaveTestCaseModal()">Cancel</button><button onclick="saveCurrentTestCase()">Save</button></div></div></div>`);
    }

    function closeSaveTestCaseModal() { $("saveTestCaseModal")?.remove(); }

    async function saveCurrentTestCase() {
      let expected;
      try { expected = JSON.parse($("saveTcExpected").value); } catch { alert("Expected JSON is invalid."); return; }
      await api("/api/admin/test-cases", { method: "POST", body: JSON.stringify({ name: $("saveTcName").value, endpoint: $("saveTcEndpoint").value, environment_code: $("saveTcEnv").value || null, input_text: $("saveTcText").value, source: "console", expected_json: expected, enabled: true, tags: $("saveTcTags").value, notes: $("saveTcNotes").value }) });
      closeSaveTestCaseModal();
    }

    async function runMatchingTestCase() {
      const endpoint = $("tEndpoint")?.value || "cmms-intake";
      const environment = $("tEnv")?.value || "";
      const text = transcriptValue();
      const cases = await api(`/api/admin/test-cases?endpoint=${encodeURIComponent(endpoint)}&environment_code=${encodeURIComponent(environment)}&enabled=true`).catch(() => []);
      const match = cases.find(c => (c.input_text || "").trim() === text.trim());
      if (!match) {
        setConsoleOutput("tOut", { error: "No enabled saved test case matched the current endpoint, environment, and input text." });
        return;
      }
      const data = await api(`/api/admin/test-cases/${match.id}/run`, { method: "POST", body: JSON.stringify({}) });
      state.lastTestResponse = data.actual_json;
      setConsoleOutput("tOut", data);
      if (data.actual_json) {
        renderContractValidation(data.actual_json.contract);
        renderTestValidation(data.actual_json.ai_validation);
        renderReadiness(data.actual_json);
        renderWorkflowTraceFromResponse(data.actual_json, "tTrace");
      }
    }

    async function createTestCaseFromTrace(runId) {
      const name = window.prompt("Test case name", `Replay ${runId}`);
      if (!name) return;
      try {
        const data = await api(`/api/admin/workflow-runs/${runId}/create-test-case`, { method: "POST", body: JSON.stringify({ name, tags: "trace", notes: `Created from workflow run ${runId}` }) });
        alert(`Created test case #${data.test_case_id}`);
      } catch (e) {
        alert(e.message);
      }
    }

    async function replayWorkflowRun(runId) {
      try {
        const data = await api(`/api/admin/workflow-runs/${runId}/replay`, { method: "POST", body: JSON.stringify({}) });
        setConsoleOutput("tOut", data);
        if ($("logTraceDetail")) $("logTraceDetail").innerHTML = data.actual_json?.trace?.run_id ? `<p class="muted">Replay created workflow run ${escapeHtml(data.actual_json.trace.run_id)}.</p>` : "<p class='muted'>Replay completed.</p>";
        if (data.actual_json) renderWorkflowTraceFromResponse(data.actual_json, "tTrace");
      } catch (e) {
        if ($("tOut")) setConsoleOutput("tOut", e.data || { error: e.message });
        if ($("logTraceDetail")) $("logTraceDetail").innerHTML = `<span class="pill danger">Replay unavailable</span><p>${escapeHtml(e.message)}</p>`;
      }
    }

    async function testCases() {
      const cases = await api("/api/admin/test-cases").catch(() => []);
      const runs = await api("/api/admin/test-case-runs?limit=25").catch(() => []);
      pageShell("Test Cases", `<div class="grid">
        <div class="card span-8"><h2>Saved Test Cases</h2><div class="card-body stack">
          <div class="command-bar"><button onclick="newTestCase()">New</button><button class="secondary" onclick="runBatchTestCases()">Run Enabled Batch</button><button class="secondary" onclick="testCases()">Refresh</button></div>
          <div id="testCaseTable">${renderTestCasesTable(cases)}</div>
        </div></div>
        <div class="card span-4"><h2>Test Case Detail</h2><div class="card-body stack detail-form" id="testCaseDetail"><p class="muted">Select a test case or create a new one.</p></div></div>
        <div class="card span-12"><h2>Recent Test Case Runs</h2><div class="card-body" id="testCaseRuns">${renderTestCaseRunsTable(runs)}</div></div>
      </div>`);
    }

    function renderTestCasesTable(rows) {
      if (!rows.length) return '<p class="muted">No saved test cases yet.</p>';
      return `<table><thead><tr><th>Name</th><th>Endpoint</th><th>Environment</th><th>Enabled</th><th>Tags</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr class="clickable-row" onclick="showTestCaseDetail(${r.id})">
          <td><strong>${escapeHtml(r.name)}</strong><div class="muted">${escapeHtml((r.input_text || "").slice(0, 80))}</div></td>
          <td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td><span class="pill ${r.enabled ? "ok" : ""}">${r.enabled ? "enabled" : "disabled"}</span></td><td>${escapeHtml(r.tags || "")}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td class="row"><button class="secondary" onclick="event.stopPropagation(); runTestCaseId(${r.id})">Run</button><button class="secondary" onclick="event.stopPropagation(); showTestCaseDetail(${r.id})">Edit</button><button class="danger" onclick="event.stopPropagation(); toggleTestCase(${r.id}, ${r.enabled ? "false" : "true"})">${r.enabled ? "Disable" : "Enable"}</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function renderTestCaseRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No test case runs recorded yet.</p>';
      return `<table><thead><tr><th>Test Case</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Status</th><th>Duration</th><th>Started</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr><td>${escapeHtml(r.test_case_name || `#${r.test_case_id}`)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.prompt_version || "")}</td><td><span class="pill ${r.status === "passed" ? "ok" : r.status === "warning" ? "warning" : "danger"}">${escapeHtml(r.status)}</span></td><td>${r.duration_ms ?? ""} ms</td><td>${escapeHtml(r.started_at || "")}</td><td class="row"><button class="secondary" onclick="viewTestCaseRun('${escapeAttr(r.id)}')">View Result</button>${r.run_id ? `<button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(r.run_id)}')">View Trace</button>` : ""}</td></tr>`).join("")}</tbody></table>`;
    }

    function testCaseEndpointOptions(selected = "cmms-intake") {
      return ["cmms-intake","cmms-assistant","extract-work-order-fields","summarize-work-order"].map(v => `<option value="${v}" ${v === selected ? "selected" : ""}>${v}</option>`).join("");
    }

    function testCaseEnvOptions(selected = "") {
      return `<option value="" ${selected ? "" : "selected"}>None / request body defaults</option>${state.envs.map(e => `<option value="${e.environment_code}" ${e.environment_code === selected ? "selected" : ""}>${e.environment_code} - ${escapeHtml(e.name)}</option>`).join("")}`;
    }

    function renderTestCaseEditor(tc = null) {
      state.selectedTestCaseId = tc?.id || null;
      const expected = tc?.expected_json || { summary_contains: [], building: null, room: null, priority: null, work_order_type: null, contract_valid: true, environment_valid: true, expected_errors: [], expected_warnings: [] };
      $("testCaseDetail").innerHTML = `<label>Name</label><input id="tcName" value="${escapeAttr(tc?.name || "New CMMS regression case")}">
        <label>Endpoint</label><select id="tcEndpoint">${testCaseEndpointOptions(tc?.endpoint || "cmms-intake")}</select>
        <label>Environment</label><select id="tcEnv">${testCaseEnvOptions(tc?.environment_code || "DEFAULT")}</select>
        <label>Input text</label><textarea id="tcInput" style="min-height:120px">${escapeHtml(tc?.input_text || "There is a water leak in ARC room 205. It looks urgent.")}</textarea>
        <label>Expected JSON</label><textarea id="tcExpected" style="min-height:260px">${escapeHtml(JSON.stringify(expected, null, 2))}</textarea>
        <label>Tags</label><input id="tcTags" value="${escapeAttr(tc?.tags || "")}">
        <label>Notes</label><textarea id="tcNotes">${escapeHtml(tc?.notes || "")}</textarea>
        <label><input id="tcEnabled" type="checkbox" ${tc?.enabled === 0 ? "" : "checked"} style="width:auto"> Enabled</label>
        <div class="button-grid"><button onclick="saveTestCaseDetail()">Save</button><button class="secondary" onclick="runSelectedTestCase()">Run</button><button class="danger" onclick="deleteSelectedTestCase()" ${tc ? "" : "disabled"}>Delete</button></div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Run result</strong>${outputToolbar("tcResult")}</div><pre id="tcResult">{}</pre></div>`;
    }

    function newTestCase() { renderTestCaseEditor(null); }

    async function showTestCaseDetail(id) {
      const tc = await api(`/api/admin/test-cases/${id}`);
      renderTestCaseEditor(tc);
    }

    async function saveTestCaseDetail() {
      let expected;
      try { expected = JSON.parse($("tcExpected").value); } catch { alert("Expected JSON is invalid."); return; }
      const payload = { name: $("tcName").value, endpoint: $("tcEndpoint").value, environment_code: $("tcEnv").value || null, input_text: $("tcInput").value, expected_json: expected, enabled: $("tcEnabled").checked, tags: $("tcTags").value, notes: $("tcNotes").value };
      if (state.selectedTestCaseId) await api(`/api/admin/test-cases/${state.selectedTestCaseId}`, { method: "PATCH", body: JSON.stringify(payload) });
      else {
        const created = await api("/api/admin/test-cases", { method: "POST", body: JSON.stringify({ ...payload, source: "manual" }) });
        state.selectedTestCaseId = created.test_case_id;
      }
      await testCases();
    }

    async function runSelectedTestCase() {
      if (!state.selectedTestCaseId) await saveTestCaseDetail();
      if (state.selectedTestCaseId) await runTestCaseId(state.selectedTestCaseId);
    }

    async function runTestCaseId(id, promptId = null) {
      const data = await api(`/api/admin/test-cases/${id}/run`, { method: "POST", body: JSON.stringify({ prompt_id: promptId }) });
      if ($("tcResult")) setConsoleOutput("tcResult", data);
      if ($("testCaseRuns")) {
        const runs = await api("/api/admin/test-case-runs?limit=25").catch(() => []);
        $("testCaseRuns").innerHTML = renderTestCaseRunsTable(runs);
      }
      return data;
    }

    async function toggleTestCase(id, enabled) {
      await api(`/api/admin/test-cases/${id}`, { method: "PATCH", body: JSON.stringify({ enabled }) });
      await testCases();
    }

    async function deleteSelectedTestCase() {
      if (!state.selectedTestCaseId || !confirm("Delete this test case?")) return;
      await api(`/api/admin/test-cases/${state.selectedTestCaseId}`, { method: "DELETE" });
      state.selectedTestCaseId = null;
      await testCases();
    }

    async function viewTestCaseRun(id) {
      const data = await api(`/api/admin/test-case-runs/${id}`);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="testRunModal"><div class="modal" style="max-width:980px"><h2>Test Case Run</h2><div class="modal-body">
        <div class="result-grid"><div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Actual JSON</strong>${outputToolbar("testRunActual")}</div><pre id="testRunActual" style="min-height:300px"></pre></div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Comparison JSON</strong>${outputToolbar("testRunCompare")}</div><pre id="testRunCompare" style="min-height:300px"></pre></div></div>
      </div><div class="modal-actions"><button class="secondary" onclick="$('testRunModal').remove()">Close</button></div></div></div>`);
      setConsoleOutput("testRunActual", data.actual_json || {});
      setConsoleOutput("testRunCompare", data.comparison_json || {});
    }

    async function runBatchTestCases(promptId = null, endpoint = null) {
      const data = await api("/api/admin/test-cases/run-batch", { method: "POST", body: JSON.stringify({ endpoint, enabled_only: true, prompt_id: promptId }) });
      if ($("tcResult")) setConsoleOutput("tcResult", data);
      else alert(`Batch complete: ${data.passed}/${data.total} passed, ${data.failed} failed, ${data.warning} warning, ${data.error} error.`);
      if ($("testCaseRuns")) {
        const runs = await api("/api/admin/test-case-runs?limit=25").catch(() => []);
        $("testCaseRuns").innerHTML = renderTestCaseRunsTable(runs);
      }
      return data;
    }

    async function testSuites() {
      const suites = await api("/api/admin/test-suites").catch(() => []);
      const runs = await api("/api/admin/test-suite-runs?limit=25").catch(() => []);
      pageShell("Test Suites", `<div class="grid">
        <div class="card span-8"><h2>Suites</h2><div class="card-body stack">
          <div class="command-bar"><button onclick="newTestSuite()">New Suite</button><button class="secondary" onclick="runAllSuites()">Run Enabled Suites</button><button class="secondary" onclick="testSuites()">Refresh</button></div>
          <div id="testSuiteTable">${renderTestSuitesTable(suites)}</div>
        </div></div>
        <div class="card span-4"><h2>Suite Detail</h2><div class="card-body stack detail-form" id="testSuiteDetail"><p class="muted">Select a suite or create a new one.</p></div></div>
        <div class="card span-12"><h2>Suite Runs</h2><div class="card-body" id="testSuiteRuns">${renderTestSuiteRunsTable(runs)}</div></div>
      </div>`);
    }

    function renderTestSuitesTable(rows) {
      if (!rows.length) return '<p class="muted">No test suites yet.</p>';
      return `<table><thead><tr><th>Name</th><th>Endpoint</th><th>Environment</th><th>Enabled</th><th>Required</th><th>Min Pass</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${rows.map(s => `
        <tr class="clickable-row" onclick="showTestSuiteDetail('${escapeAttr(s.suite_id)}')"><td><strong>${escapeHtml(s.name)}</strong><div class="muted">${escapeHtml(s.tags || "")}</div></td><td>${escapeHtml(s.endpoint)}</td><td>${escapeHtml(s.environment_code || "")}</td><td><span class="pill ${s.enabled ? "ok" : ""}">${s.enabled ? "enabled" : "disabled"}</span></td><td>${s.required_for_promotion ? "Yes" : "No"}</td><td>${s.min_pass_rate}</td><td>${escapeHtml(s.updated_at || "")}</td><td class="row"><button class="secondary" onclick="event.stopPropagation(); showTestSuiteDetail('${escapeAttr(s.suite_id)}')">Edit</button><button class="secondary" onclick="event.stopPropagation(); runTestSuiteId('${escapeAttr(s.suite_id)}')">Run</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderTestSuiteRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No suite runs recorded yet.</p>';
      return `<table><thead><tr><th>Suite</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Status</th><th>Pass Rate</th><th>Started</th><th>Actions</th></tr></thead><tbody>${rows.map(r => {
        const s = r.summary_json || {};
        return `<tr><td>${escapeHtml(r.suite_name || r.suite_id)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.prompt_version || "")}</td><td><span class="pill ${r.status === "passed" ? "ok" : r.status === "warning" ? "warning" : "danger"}">${escapeHtml(r.status)}</span></td><td>${s.pass_rate ?? ""}</td><td>${escapeHtml(r.started_at || "")}</td><td><button class="secondary" onclick="viewTestSuiteRun('${escapeAttr(r.suite_run_id)}')">View</button></td></tr>`;
      }).join("")}</tbody></table>`;
    }

    function renderTestSuiteEditor(suite = null) {
      const selectedEnv = suite?.environment_code || "DEFAULT";
      $("testSuiteDetail").innerHTML = `<label>Name</label><input id="tsName" value="${escapeAttr(suite?.name || "CMMS Intake Regression Suite")}">
        <label>Endpoint</label><select id="tsEndpoint">${testCaseEndpointOptions(suite?.endpoint || "cmms-intake")}</select>
        <label>Environment</label><select id="tsEnv">${testCaseEnvOptions(selectedEnv)}</select>
        <label>Description</label><textarea id="tsDescription">${escapeHtml(suite?.description || "")}</textarea>
        <label>Min pass rate</label><input id="tsMinPass" type="number" min="0" max="1" step="0.01" value="${suite?.min_pass_rate ?? 1}">
        <label><input id="tsEnabled" type="checkbox" ${suite?.enabled === 0 ? "" : "checked"} style="width:auto"> Enabled</label>
        <label><input id="tsRequired" type="checkbox" ${suite?.required_for_promotion ? "checked" : ""} style="width:auto"> Required for promotion</label>
        <label><input id="tsZeroError" type="checkbox" ${suite?.zero_error_required === 0 ? "" : "checked"} style="width:auto"> Zero error required</label>
        <label><input id="tsZeroRegression" type="checkbox" ${suite?.zero_regression_required === 0 ? "" : "checked"} style="width:auto"> Zero regression required</label>
        <label>Tags</label><input id="tsTags" value="${escapeAttr(suite?.tags || "")}">
        <div class="button-grid"><button onclick="saveTestSuite('${escapeAttr(suite?.suite_id || "")}')">Save</button><button class="secondary" onclick="runSelectedSuite('${escapeAttr(suite?.suite_id || "")}')">Run Suite</button><button class="danger" onclick="deleteTestSuite('${escapeAttr(suite?.suite_id || "")}')" ${suite ? "" : "disabled"}>Delete</button></div>
        <h3>Cases</h3><div id="suiteCases">${suite ? renderSuiteCases(suite.cases || []) : '<p class="muted">Save the suite before adding cases.</p>'}</div>
        ${suite ? `<label>Add Test Case ID</label><input id="suiteAddCaseId" placeholder="Test case id"><button class="secondary" onclick="addCaseToSuite('${escapeAttr(suite.suite_id)}')">Add Test Case</button>` : ""}
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Suite output</strong>${outputToolbar("suiteResult")}</div><pre id="suiteResult">{}</pre></div>`;
    }

    function renderSuiteCases(cases) {
      if (!cases.length) return '<p class="muted">No cases assigned.</p>';
      return `<table><thead><tr><th>ID</th><th>Name</th><th>Enabled</th><th>Action</th></tr></thead><tbody>${cases.map(c => `<tr><td>${c.test_case_id}</td><td>${escapeHtml(c.name)}</td><td>${c.enabled ? "Yes" : "No"}</td><td><button class="danger" onclick="removeCaseFromSuite('${escapeAttr(c.suite_id)}', ${c.test_case_id})">Remove</button></td></tr>`).join("")}</tbody></table>`;
    }

    function newTestSuite() { renderTestSuiteEditor(null); }

    async function showTestSuiteDetail(suiteId) {
      const suite = await api(`/api/admin/test-suites/${suiteId}`);
      renderTestSuiteEditor(suite);
    }

    async function saveTestSuite(suiteId) {
      const payload = { name: $("tsName").value, endpoint: $("tsEndpoint").value, environment_code: $("tsEnv").value || null, description: $("tsDescription").value, enabled: $("tsEnabled").checked, required_for_promotion: $("tsRequired").checked, min_pass_rate: Number($("tsMinPass").value), zero_error_required: $("tsZeroError").checked, zero_regression_required: $("tsZeroRegression").checked, tags: $("tsTags").value };
      if (suiteId) await api(`/api/admin/test-suites/${suiteId}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await api("/api/admin/test-suites", { method: "POST", body: JSON.stringify(payload) });
      await testSuites();
    }

    async function addCaseToSuite(suiteId) {
      await api(`/api/admin/test-suites/${suiteId}/cases`, { method: "POST", body: JSON.stringify({ test_case_id: Number($("suiteAddCaseId").value) }) });
      await showTestSuiteDetail(suiteId);
    }

    async function removeCaseFromSuite(suiteId, testCaseId) {
      await api(`/api/admin/test-suites/${suiteId}/cases/${testCaseId}`, { method: "DELETE" });
      await showTestSuiteDetail(suiteId);
    }

    async function runSelectedSuite(suiteId) {
      if (!suiteId) { alert("Save the suite before running."); return; }
      await runTestSuiteId(suiteId);
    }

    async function runTestSuiteId(suiteId, promptId = null) {
      const data = await api(`/api/admin/test-suites/${suiteId}/run`, { method: "POST", body: JSON.stringify({ prompt_id: promptId }) });
      if ($("suiteResult")) setConsoleOutput("suiteResult", data);
      await refreshTestSuiteRuns();
      return data;
    }

    async function refreshTestSuiteRuns() {
      if (!$("testSuiteRuns")) return;
      const runs = await api("/api/admin/test-suite-runs?limit=25").catch(() => []);
      $("testSuiteRuns").innerHTML = renderTestSuiteRunsTable(runs);
    }

    async function runAllSuites(promptId = null, endpoint = null, requiredOnly = false) {
      const data = await api("/api/admin/test-suites/run-batch", { method: "POST", body: JSON.stringify({ prompt_id: promptId, endpoint, required_only: requiredOnly, enabled_only: true }) });
      if ($("suiteResult")) setConsoleOutput("suiteResult", data);
      else alert(`Suite batch complete: ${data.passed}/${data.total_suites} passed, ${data.failed} failed, ${data.error} error.`);
      await refreshTestSuiteRuns();
      return data;
    }

    async function viewTestSuiteRun(suiteRunId) {
      const data = await api(`/api/admin/test-suite-runs/${suiteRunId}`);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="suiteRunModal"><div class="modal" style="max-width:1040px"><h2>Suite Run</h2><div class="modal-body">
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Suite run JSON</strong>${outputToolbar("suiteRunOut")}</div><pre id="suiteRunOut" style="min-height:360px"></pre></div>
      </div><div class="modal-actions"><button class="secondary" onclick="$('suiteRunModal').remove()">Close</button></div></div></div>`);
      setConsoleOutput("suiteRunOut", data);
    }

    async function deleteTestSuite(suiteId) {
      if (!suiteId || !confirm("Delete this test suite?")) return;
      await api(`/api/admin/test-suites/${suiteId}`, { method: "DELETE" });
      await testSuites();
    }

    function builder() {
      const base = location.origin;
      pageShell("API Call Builder", `<div class="grid">
        <div class="card span-4"><h2>Inputs</h2><div class="card-body stack">
          <label>Base URL</label><input id="bBase" value="${base}">
          <label>API key</label><input id="bKey" value="${escapeAttr(state.defaultApiKey)}">
          <label>Endpoint</label><select id="bEndpoint" onchange="buildCall()"><option value="cmms-intake">CMMS Intake</option><option value="cmms-assistant">CMMS Assistant</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select>
          <label>Environment</label><select id="bEnv" onchange="buildCall()">${envOptions()}</select>
          <label>Input source</label><select id="bSource" onchange="buildCall()"><option value="text">text</option><option value="voice_transcript">voice_transcript</option></select>
          <label>Text</label><textarea id="bText" oninput="buildCall()">The air conditioner in ARC room 205 is making loud noise.</textarea>
          <label><input id="bReturnValidation" type="checkbox" checked style="width:auto" onchange="buildCall()"> Include readiness validation in examples</label>
          <div class="button-grid"><button onclick="buildCall()">Generate</button><button class="secondary" onclick="runBuilderValidation()">Run + Validate</button></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Generated calls</div><div class="playground-subtitle">PowerShell, curl, request body, response contract, and readiness logic.</div></div><span class="pill">Builder</span></div><div class="run-surface">
          <div id="bDoc" class="ai-panel"></div>
          <div id="bValidationOut" class="readiness warn"><strong>Validation preview</strong><div class="muted">Use Run + Validate to call the endpoint and check whether the response has enough validated information.</div></div>
          <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Generated examples</strong>${outputToolbar("bOut")}</div><pre id="bOut" class="code-output"></pre></div>
        </div></div>
      </div>`);
      buildCall();
    }
    function buildCall() {
      const ep = $("bEndpoint").value;
      const bodyObj = { text: $("bText").value, environment_code: $("bEnv").value };
      if ($("bSource").value !== "text") bodyObj.source = $("bSource").value;
      const body = JSON.stringify(bodyObj, null, 2);
      const uri = `${$("bBase").value}/api/ai/${ep}`;
      const includeValidation = $("bReturnValidation").checked && ep === "cmms-intake";
      const psValidation = includeValidation ? `\n\n# Readiness check: advisory only, does not create a work order\n$ContractOk = $Response.contract.valid\n$EnvironmentOk = $Response.ai_validation.valid\n$CanCreateWorkOrder = $Response.validation.can_create_work_order\n$MissingFields = $Response.validation.missing_fields -join ", "\n[pscustomobject]@{\n  ContractValidation = $ContractOk\n  EnvironmentValidation = $EnvironmentOk\n  EnoughInformation = $CanCreateWorkOrder\n  MissingFields = $MissingFields\n  AdvisoryOnly = $true\n}` : "";
      const ps = `$Headers = @{ "x-api-key" = "${$("bKey").value}" }\n$Body = @'\n${body}\n'@\n$Response = Invoke-RestMethod -Method POST -Uri "${uri}" -Headers $Headers -ContentType "application/json" -Body $Body\n$Response | ConvertTo-Json -Depth 20${psValidation}`;
      const curl = `curl -X POST "${uri}" \\\n  -H "x-api-key: ${$("bKey").value}" \\\n  -H "Content-Type: application/json" \\\n  -d '${body.replaceAll("'", "\\'")}'`;
      const responseNotes = endpointDoc(ep, includeValidation);
      $("bDoc").innerHTML = responseNotes;
      setConsoleOutput("bOut", `PowerShell:\n${ps}\n\ncurl:\n${curl}\n\nJSON body:\n${body}\n\nExpected response fields:\n${expectedFields(ep).join("\\n")}`, false);
    }

    function endpointDoc(endpoint, includeValidation) {
      const docs = {
        "cmms-intake": ["POST /api/ai/cmms-intake", "Returns endpoint, environment_code, contract validation, result, ai_validation, advisory validation, drafts, and model.", "Use contract.valid plus ai_validation.valid plus validation.can_create_work_order to decide if the request has enough information for a human-controlled CMMS workflow."],
        "cmms-assistant": ["POST /api/ai/cmms-assistant", "Returns a controlled conversational CMMS assistant response and safety flags.", "This is not a generic /chat endpoint. It is advisory-only and cannot write to CMMS, create work orders, or send emails."],
        "extract-work-order-fields": ["POST /api/ai/extract-work-order-fields", "Returns extracted request_type, building, room, priority, summary, missing_fields, needs_human_review, and confidence.", "Use missing_fields and needs_human_review to decide if a human must complete the request."],
        "summarize-work-order": ["POST /api/ai/summarize-work-order", "Returns one summary string.", "This endpoint does not validate work order readiness."]
      };
      const lines = docs[endpoint] || docs["cmms-intake"];
      return `<strong>${escapeHtml(lines[0])}</strong><p class="muted">${escapeHtml(lines[1])}</p><p>${escapeHtml(lines[2])}</p>${includeValidation ? '<span class="pill ok">Readiness logic included</span>' : '<span class="pill">Readiness logic not applicable</span>'}`;
    }

    function expectedFields(endpoint) {
      if (endpoint === "summarize-work-order") return ["- summary: string"];
      if (endpoint === "cmms-assistant") return ["- mode: cmms-assistant", "- response: string", "- model: qwen3:8b", "- safety.advisory_only: true", "- safety.work_order_created: false"];
      if (endpoint === "extract-work-order-fields") return ["- request_type: string", "- building: string|null", "- room: string|null", "- priority: string", "- missing_fields: array", "- needs_human_review: boolean", "- confidence: number"];
      return ["- contract.valid: boolean", "- result: normalized contract payload", "- ai_validation.valid: boolean|null", "- ai_validation.errors/warnings/normalized", "- validation.can_create_work_order: boolean advisory flag", "- validation.missing_fields: array", "- drafts: advisory text only"];
    }

    async function runBuilderValidation() {
      const ep = $("bEndpoint").value;
      const body = { text: $("bText").value, environment_code: $("bEnv").value };
      if ($("bSource").value !== "text") body.source = $("bSource").value;
      try {
        const data = await api(`/api/ai/${ep}`, { method: "POST", headers: { "x-api-key": $("bKey").value }, body: JSON.stringify(body) });
        if (ep === "cmms-intake") {
          const summary = readinessSummary(data);
          $("bValidationOut").className = `readiness ${summary.cls}`;
          $("bValidationOut").innerHTML = summary.html;
        } else if (ep === "extract-work-order-fields") {
          $("bValidationOut").className = `readiness ${data.needs_human_review ? "warn" : ""}`;
          $("bValidationOut").innerHTML = `<strong>${data.needs_human_review ? "Needs human review" : "Basic extraction complete"}</strong><div class="muted">Missing fields: ${(data.missing_fields || []).join(", ") || "none"}</div>`;
        } else if (ep === "cmms-assistant") {
          $("bValidationOut").className = "readiness warn";
          $("bValidationOut").innerHTML = '<strong>Assistant response</strong><div class="muted">Controlled advisory chat only. No readiness validation and no CMMS action.</div>';
        } else {
          $("bValidationOut").className = "readiness warn";
          $("bValidationOut").innerHTML = '<strong>Summary only</strong><div class="muted">This endpoint does not return readiness validation.</div>';
        }
        setConsoleOutput("bOut", `${formatConsoleOutput("bOut")}\n\nLive response:\n${JSON.stringify(data, null, 2)}`, false);
      } catch (e) {
        $("bValidationOut").className = "readiness fail";
        $("bValidationOut").innerHTML = `<strong>API call failed</strong><div class="muted">${escapeHtml(e.message)}</div>`;
      }
    }
    async function environments() {
      await refreshBase();
      if (!state.envs.some(e => e.environment_code === state.selectedEnv)) state.selectedEnv = state.envs[0]?.environment_code || "DEFAULT";
      await loadEnvironmentCodes();
      await loadValidationRules();
      const env = state.envs.find(e => e.environment_code === state.selectedEnv) || {};
      pageShell("Environments", `<div class="resource-header">
        <div class="resource-title">Environment: ${env.environment_code || state.selectedEnv}</div>
        <div class="muted">Status: ${env.enabled ? "Enabled" : "Disabled"} &nbsp; Model: qwen3:8b &nbsp; Base URL: local &nbsp; Updated: ${env.updated_at || ""}</div>
      </div>
      <div class="command-bar">
        <span class="muted">Environment</span><select id="envPick" onchange="state.selectedEnv=this.value; environments()">${state.envs.map(e=>`<option value="${e.environment_code}" ${e.environment_code===state.selectedEnv?"selected":""}>${e.environment_code} - ${e.name}</option>`).join("")}</select>
        <button class="secondary" onclick="showCreateEnv()">Create environment</button>
        <button class="secondary" onclick="environments()">Refresh</button>
      </div>
      <div class="tabs">
        <button class="${state.envTab==='codes'?'active':''}" onclick="state.envTab='codes'; renderEnvironmentTab()">Code Lists</button>
        <button class="${state.envTab==='validation'?'active':''}" onclick="state.envTab='validation'; renderEnvironmentTab()">Validation Rules</button>
        <button disabled>Overview</button><button disabled>Test Console</button><button disabled>API Examples</button><button disabled>Usage Logs</button><button disabled>Settings</button>
      </div>
      <div id="envTab">${state.envTab === 'validation' ? renderValidationRulesTab() : renderCodeListsTab()}</div>`);
    }
    async function createEnv() {
      await api("/api/admin/environments", { method: "POST", body: JSON.stringify({ environment_code: $("envCode").value, name: $("envName").value, enabled: true }) });
      await refreshBase(); environments();
    }

    function showCreateEnv() {
      const code = prompt("Environment code", "TEST");
      if (!code) return;
      const name = prompt("Environment name", "Test Environment") || code;
      api("/api/admin/environments", { method: "POST", body: JSON.stringify({ environment_code: code, name, enabled: true }) }).then(async () => { await refreshBase(); state.selectedEnv = code.toUpperCase(); environments(); });
    }

    async function loadEnvironmentCodes() {
      state.codeData = await api(`/api/admin/environments/${state.selectedEnv}/codes`).catch(() => ({ rows: [] }));
    }

    async function loadValidationRules() {
      state.validationRules = await api(`/api/environments/${state.selectedEnv}/validation-rules`).catch(() => []);
    }

    function renderEnvironmentTab() {
      $("envTab").innerHTML = state.envTab === "validation" ? renderValidationRulesTab() : renderCodeListsTab();
    }

    function currentCodeRows() {
      const search = ($("codeSearch")?.value || "").toLowerCase();
      return (state.codeData?.rows || []).filter(r => r.category === state.selectedCategory).filter(r => !search || `${r.code} ${r.label} ${r.aliases || ""}`.toLowerCase().includes(search));
    }

    function categoryLabel(category) {
      return (codeCategories.find(c => c[0] === category) || [category, category])[1];
    }

    function renderCodeListsTab() {
      const rows = currentCodeRows();
      const selected = state.selectedCode || rows[0] || null;
      state.selectedCode = selected;
      return `<div class="command-bar">
        <strong>Code Lists</strong><span class="muted">Manage controlled input values used by AI extraction and validation.</span>
        <select id="codeCategory" onchange="changeCodeCategory(this.value)">${codeCategories.map(([v,l])=>`<option value="${v}" ${v===state.selectedCategory?"selected":""}>${l}</option>`).join("")}</select>
        <input id="codeSearch" placeholder="Search code or description" oninput="renderCodesOnly()">
        <button onclick="openImportModal()">Import</button><button class="secondary" onclick="exportCodes()">Export</button><button class="secondary" onclick="validateSample()">Validate Sample</button><button class="secondary" onclick="environments()">Refresh</button>
      </div>
      <div class="muted" style="margin-bottom:10px">Environment: <strong>${state.selectedEnv}</strong> / Category: <strong>${categoryLabel(state.selectedCategory)}</strong></div>
      <div class="blade-layout">
        <div class="card"><h2>${categoryLabel(state.selectedCategory)}</h2><div class="card-body">${renderCodeTable(rows)}</div></div>
        <div class="blade" id="codeBlade">${renderCodeBlade(selected)}</div>
      </div>`;
    }

    function renderCodesOnly() {
      state.selectedCategory = $("codeCategory").value;
      $("envTab").innerHTML = renderCodeListsTab();
    }

    async function changeCodeCategory(category) {
      state.selectedCategory = category;
      state.selectedCode = null;
      await loadEnvironmentCodes();
      renderCodesOnly();
    }

    function renderCodeTable(rows) {
      if (!rows.length) return `<p class="muted">No codes for this category. Use Import to add values.</p>`;
      return `<table><thead><tr><th>Code</th><th>Description</th><th>Status</th><th>Source</th><th>Updated At</th><th>Actions</th></tr></thead><tbody>${rows.map(r=>`
        <tr class="clickable-row" onclick="selectCode(${r.code_id})">
          <td><strong>${escapeHtml(r.code)}</strong></td><td>${escapeHtml(r.label || "")}</td><td>${r.enabled ? '<span class="pill ok">Enabled</span>' : '<span class="pill danger">Disabled</span>'}</td><td>${escapeHtml(r.source || "Manual")}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td><button class="secondary" onclick="event.stopPropagation(); selectCode(${r.code_id})">Edit</button> <button class="secondary" onclick="event.stopPropagation(); disableCode(${r.code_id})">Disable</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function selectCode(codeId) {
      state.selectedCode = (state.codeData?.rows || []).find(r => r.code_id === codeId);
      $("codeBlade").innerHTML = renderCodeBlade(state.selectedCode);
    }

    function renderCodeBlade(row) {
      if (!row) return `<h2>Edit Code</h2><div class="blade-body muted">Select a code row to edit details.</div>`;
      const defaultMetadata = JSON.stringify({ site: "main", active: true }, null, 2);
      return `<h2>Edit Code</h2><div class="blade-body stack">
        <label>Code</label><input id="editCode" value="${escapeAttr(row.code)}">
        <label>Description</label><input id="editLabel" value="${escapeAttr(row.label || "")}">
        <label>Aliases</label><input id="editAliases" value="${escapeAttr(row.aliases || "")}" placeholder="ARC, Arc Building">
        <label>Metadata JSON</label><textarea id="editMetadata">${escapeHtml(row.metadata_json || defaultMetadata)}</textarea>
        <div class="row"><button onclick="saveCode(${row.code_id})">Save</button><button class="danger" onclick="disableCode(${row.code_id})">Disable</button></div>
      </div>`;
    }

    async function saveCode(codeId) {
      await api(`/api/admin/environments/${state.selectedEnv}/codes/${codeId}`, { method: "PATCH", body: JSON.stringify({ code: $("editCode").value, label: $("editLabel").value, aliases: $("editAliases").value, metadata_json: $("editMetadata").value, enabled: true }) });
      await loadEnvironmentCodes(); renderCodesOnly();
    }

    async function disableCode(codeId) {
      await api(`/api/admin/environments/${state.selectedEnv}/codes/${codeId}`, { method: "PATCH", body: JSON.stringify({ enabled: false }) });
      await loadEnvironmentCodes(); renderCodesOnly();
    }

    function openImportModal() {
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="importModal"><div class="modal"><h2>Import ${categoryLabel(state.selectedCategory)}</h2><div class="modal-body stack">
        <p class="muted">Paste codes or upload a CSV file. Format: Code, Description, Aliases, Metadata JSON</p>
        <label>CSV file</label><input id="importFile" type="file" accept=".csv,text/csv" onchange="readImportFile()">
        <textarea id="importText">ARC, ARC Building\nCAMPUSVIEW, Campus View\nZONE-18, Zone 18</textarea>
        <label><input id="importReplace" type="checkbox" style="width:auto"> Replace this category before importing</label>
        <div id="previewBox" class="muted">Preview results will appear here.</div>
      </div><div class="modal-actions"><button class="secondary" onclick="closeImportModal()">Cancel</button><button class="secondary" onclick="previewImport()">Preview Import</button><button onclick="commitImport()">Import</button></div></div></div>`);
    }

    function closeImportModal() { $("importModal")?.remove(); }

    function readImportFile() {
      const file = $("importFile")?.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => { $("importText").value = String(reader.result || ""); previewImport(); };
      reader.onerror = () => { $("previewBox").innerHTML = '<span class="pill danger">Could not read CSV file.</span>'; };
      reader.readAsText(file);
    }

    async function previewImport() {
      const data = await api(`/api/admin/environments/${state.selectedEnv}/codes/preview`, { method: "POST", body: JSON.stringify({ category: state.selectedCategory, text: $("importText").value, replace: $("importReplace")?.checked || false }) });
      $("previewBox").innerHTML = `<div class="preview-summary"><div><strong>${data.valid_count}</strong><br>valid</div><div><strong>${data.duplicate_count}</strong><br>duplicates</div><div><strong>${data.invalid_count}</strong><br>invalid</div><div><strong>${data.update_count}</strong><br>existing updated</div><div><strong>${data.insert_count}</strong><br>new inserted</div></div>${renderImportPreviewTable(data)}`;
    }

    async function commitImport() {
      await api(`/api/admin/environments/${state.selectedEnv}/codes/import`, { method: "POST", body: JSON.stringify({ category: state.selectedCategory, text: $("importText").value, replace: $("importReplace")?.checked || false }) });
      closeImportModal(); await loadEnvironmentCodes(); renderCodesOnly();
    }

    function renderImportPreviewTable(data) {
      const rows = (data.valid || []).slice(0, 25);
      if (!rows.length) return '<p class="muted">No valid rows in preview.</p>';
      return `<table><thead><tr><th>Code</th><th>Description</th><th>Aliases</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td><strong>${escapeHtml(r.code)}</strong></td><td>${escapeHtml(r.label || "")}</td><td>${escapeHtml(r.aliases || "")}</td><td>${(data.category && (data.valid || []).some(x => x.code === r.code)) ? "Import/update" : "Import"}</td></tr>`).join("")}</tbody></table>`;
    }

    function exportCodes() {
      const csv = currentCodeRows().map(r => [r.code, r.label || "", r.aliases || ""].map(v => `"${String(v).replaceAll('"','""')}"`).join(",")).join("\\n");
      navigator.clipboard?.writeText(csv); alert("Current table copied as CSV.");
    }

    function validateSample() { alert("Validation Rules is the next resource tab. For now, code-list duplicate and metadata validation run during import/edit."); }

    function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
    function escapeAttr(value) { return escapeHtml(value).replaceAll("`", "&#96;"); }

    function renderValidationRulesTab() {
      return `<div class="command-bar">
        <strong>Validation Rules</strong><span class="muted">These rules validate AI output after extraction. They do not change the model prompt.</span>
        <button class="secondary" onclick="resetValidationRules()">Reset Defaults</button>
        <button class="secondary" onclick="openValidateSampleModal()">Validate Sample</button>
        <button class="secondary" onclick="refreshValidationRules()">Refresh</button>
      </div>
      <div class="card"><h2>Rules</h2><div class="card-body">${renderValidationTable()}</div></div>`;
    }

    function renderValidationTable() {
      if (!state.validationRules.length) return '<p class="muted">No validation rules configured.</p>';
      return `<table><thead><tr><th>Field</th><th>Required</th><th>Match Code List</th><th>Category</th><th>Allow Unknown</th><th>Severity</th><th>Enabled</th><th>Actions</th></tr></thead><tbody>${state.validationRules.map(r=>`
        <tr>
          <td><strong>${escapeHtml(r.label)}</strong><div class="muted">${escapeHtml(r.field_name)}</div></td>
          <td>${r.required ? "Yes" : "No"}</td>
          <td>${r.must_match_code_list ? "Yes" : "No"}</td>
          <td>${escapeHtml(r.code_category || "")}</td>
          <td>${r.allow_unknown ? "Yes" : "No"}</td>
          <td>${r.severity === "error" ? '<span class="pill danger">Error</span>' : '<span class="pill">Warning</span>'}</td>
          <td>${r.enabled ? '<span class="pill ok">Yes</span>' : '<span class="pill danger">No</span>'}</td>
          <td><button class="secondary" onclick="editValidationRule(${r.id})">Edit</button> <button class="secondary" onclick="toggleValidationRule(${r.id}, ${r.enabled ? "false" : "true"})">${r.enabled ? "Disable" : "Enable"}</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    async function refreshValidationRules() {
      await loadValidationRules();
      renderEnvironmentTab();
    }

    async function toggleValidationRule(ruleId, enabled) {
      await api(`/api/admin/environments/${state.selectedEnv}/validation-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify({ enabled }) });
      await refreshValidationRules();
    }

    function editValidationRule(ruleId) {
      const rule = state.validationRules.find(r => r.id === ruleId);
      if (!rule) return;
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="ruleModal"><div class="modal"><h2>Edit ${escapeHtml(rule.label)}</h2><div class="modal-body stack">
        <label><input id="ruleEnabled" type="checkbox" ${rule.enabled ? "checked" : ""} style="width:auto"> Enabled</label>
        <label><input id="ruleRequired" type="checkbox" ${rule.required ? "checked" : ""} style="width:auto"> Required</label>
        <label><input id="ruleMatch" type="checkbox" ${rule.must_match_code_list ? "checked" : ""} style="width:auto"> Must match code list</label>
        <label><input id="ruleUnknown" type="checkbox" ${rule.allow_unknown ? "checked" : ""} style="width:auto"> Allow unknown value</label>
        <label>Category mapping</label><select id="ruleCategory">${codeCategories.map(([v,l])=>`<option value="${v}" ${v===rule.code_category?"selected":""}>${l}</option>`).join("")}</select>
        <label>Severity</label><select id="ruleSeverity"><option value="error" ${rule.severity==="error"?"selected":""}>error</option><option value="warning" ${rule.severity==="warning"?"selected":""}>warning</option></select>
      </div><div class="modal-actions"><button class="secondary" onclick="closeRuleModal()">Cancel</button><button onclick="saveValidationRule(${rule.id})">Save</button></div></div></div>`);
    }

    function closeRuleModal() { $("ruleModal")?.remove(); }

    async function saveValidationRule(ruleId) {
      await api(`/api/admin/environments/${state.selectedEnv}/validation-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify({ enabled: $("ruleEnabled").checked, required: $("ruleRequired").checked, must_match_code_list: $("ruleMatch").checked, allow_unknown: $("ruleUnknown").checked, code_category: $("ruleCategory").value, severity: $("ruleSeverity").value }) });
      closeRuleModal(); await refreshValidationRules();
    }

    async function resetValidationRules() {
      if (!confirm("Reset validation rules for this environment to defaults?")) return;
      await api(`/api/admin/environments/${state.selectedEnv}/validation-rules/reset-defaults`, { method: "POST" });
      await refreshValidationRules();
    }

    function openValidateSampleModal() {
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="sampleModal"><div class="modal"><h2>Validate Sample</h2><div class="modal-body stack">
        <textarea id="sampleJson">{\n  "building": "ARC",\n  "room": "101",\n  "priority": "HIGH",\n  "work_order_type": "PM",\n  "assign_to": "1001",\n  "issue_to": "2001",\n  "job_type": "ELEC"\n}</textarea>
        <div id="sampleResult" class="muted">Run validation to see pass/fail.</div>
      </div><div class="modal-actions"><button class="secondary" onclick="closeSampleModal()">Close</button><button onclick="runSampleValidation()">Validate</button></div></div></div>`);
    }

    function closeSampleModal() { $("sampleModal")?.remove(); }

    async function runSampleValidation() {
      let values;
      try { values = JSON.parse($("sampleJson").value); } catch { $("sampleResult").innerHTML = '<span class="pill danger">Invalid JSON</span>'; return; }
      const data = await api(`/api/environments/${state.selectedEnv}/validate-sample`, { method: "POST", body: JSON.stringify({ values }) });
      $("sampleResult").innerHTML = `<div class="pill ${data.valid ? "ok" : "danger"}">${data.valid ? "Passed" : "Failed"}</div><pre style="min-height:160px">${JSON.stringify(data, null, 2)}</pre>`;
    }
    async function contracts() {
      const data = await api("/api/admin/output-contracts");
      pageShell("AI Output Contracts", `<div class="contracts-layout">
        <div class="card"><h2>Contracts</h2><div class="card-body">${renderContractsTable(data)}</div></div>
        <div class="card"><h2>Contract Detail</h2><div class="card-body stack detail-form" id="contractDetail"><p class="muted">Select a contract to view or edit.</p></div></div>
      </div>`);
    }

    function renderContractsTable(rows) {
      if (!rows.length) return '<p class="muted">No output contracts configured.</p>';
      return `<table><thead><tr><th>Endpoint</th><th>Version</th><th>Status</th><th>Strict Mode</th><th>Updated At</th><th>Actions</th></tr></thead><tbody>${rows.map(r=>`
        <tr class="clickable-row" onclick='showContractDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>
          <td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.version)}</td><td>${r.status === "active" ? '<span class="pill ok">active</span>' : `<span class="pill">${escapeHtml(r.status)}</span>`}</td><td>${r.strict_mode ? "Yes" : "No"}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td><button class="secondary" onclick='event.stopPropagation(); showContractDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>View / Edit / Test</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function showContractDetail(contract) {
      $("contractDetail").innerHTML = `<label>Endpoint</label><input id="contractEndpoint" value="${escapeAttr(contract.endpoint)}" disabled>
        <label>Version</label><input id="contractVersion" value="${escapeAttr(contract.version)}" disabled>
        <label>Name</label><input id="contractName" value="${escapeAttr(contract.name)}">
        <label>Status</label><select id="contractStatus"><option ${contract.status==="draft"?"selected":""}>draft</option><option ${contract.status==="active"?"selected":""}>active</option><option ${contract.status==="archived"?"selected":""}>archived</option></select>
        <label><input id="contractStrict" type="checkbox" ${contract.strict_mode ? "checked" : ""} style="width:auto"> Strict mode</label>
        <label>Schema JSON</label><textarea id="contractSchema" style="min-height:360px">${escapeHtml(JSON.stringify(contract.schema_json, null, 2))}</textarea>
        <label>Sample Payload</label><textarea id="contractSample">{
  "summary": "Air conditioner in ARC room 205 is noisy.",
  "building": "ARC",
  "room": "205",
  "priority": "NORMAL",
  "work_order_type": "HVAC",
  "assign_to": null,
  "issue_to": null,
  "job_type": null,
  "confidence": 0.86
}</textarea>
        <div class="row"><button onclick="saveContract(${contract.id})">Save</button><button class="secondary" onclick="activateContract(${contract.id})">Activate</button><button class="secondary" onclick="testContract(${contract.id})">Test Sample</button></div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Sample validation</strong>${outputToolbar("contractResult")}</div><pre id="contractResult" style="min-height:160px">{}</pre></div>`;
    }

    async function saveContract(id) {
      let schema;
      try { schema = JSON.parse($("contractSchema").value); } catch { alert("Schema JSON is invalid."); return; }
      await api(`/api/admin/output-contracts/${id}`, { method: "PATCH", body: JSON.stringify({ name: $("contractName").value, status: $("contractStatus").value, schema_json: schema, strict_mode: $("contractStrict").checked }) });
      contracts();
    }

    async function activateContract(id) {
      await api(`/api/admin/output-contracts/${id}/activate`, { method: "POST" });
      contracts();
    }

    async function testContract(id) {
      let values;
      try { values = JSON.parse($("contractSample").value); } catch { setConsoleOutput("contractResult", { error: "Invalid sample JSON" }); return; }
      const data = await api(`/api/admin/output-contracts/${id}/validate-sample`, { method: "POST", body: JSON.stringify({ values }) });
      setConsoleOutput("contractResult", data);
    }

    async function prompts() {
      const data = await api("/api/admin/prompt-versions");
      const comparisons = await api("/api/admin/prompt-comparisons?limit=25").catch(() => []);
      const promotions = await api("/api/admin/prompt-promotions?limit=25").catch(() => []);
      pageShell("Prompt Versions", `<div class="contracts-layout">
        <div class="card"><h2>Prompts</h2><div class="card-body">${renderPromptsTable(data)}</div></div>
        <div class="card"><h2>Prompt Detail</h2><div class="card-body stack detail-form" id="promptDetail"><p class="muted">Select a prompt to view, test, edit, activate, or archive.</p></div></div>
        <div class="card"><h2>Prompt Comparisons</h2><div class="card-body" id="promptComparisons">${renderPromptComparisonsTable(comparisons)}</div></div>
        <div class="card"><h2>Comparison Detail</h2><div class="card-body" id="promptComparisonDetail"><p class="muted">Run or view a comparison to see deterministic regression results.</p></div></div>
        <div class="card"><h2>Promotion History</h2><div class="card-body" id="promptPromotions">${renderPromptPromotionsTable(promotions)}</div></div>
      </div>`);
    }

    function renderPromptsTable(rows) {
      if (!rows.length) return '<p class="muted">No prompt versions configured.</p>';
      return `<table><thead><tr><th>Endpoint</th><th>Version</th><th>Status</th><th>Model</th><th>Temperature</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr class="clickable-row" onclick='showPromptDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>
          <td><strong>${escapeHtml(r.endpoint)}</strong><div class="muted">${escapeHtml(r.name)}</div></td>
          <td>${escapeHtml(r.version)}</td>
          <td><span class="pill ${r.status === "active" ? "ok" : r.status === "archived" ? "danger" : ""}">${escapeHtml(r.status)}</span></td>
          <td>${escapeHtml(r.model)}</td><td>${r.temperature}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td><button class="secondary" onclick='event.stopPropagation(); showPromptDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>View / Test</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function showPromptDetail(prompt) {
      const readonly = prompt.status === "archived" ? "disabled" : "";
      $("promptDetail").innerHTML = `<div class="row"><span class="pill ${prompt.status === "active" ? "ok" : prompt.status === "archived" ? "danger" : ""}">${escapeHtml(prompt.status)}</span><span class="muted">${escapeHtml(prompt.endpoint)} / ${escapeHtml(prompt.version)}</span></div>
        <label>Endpoint</label><input id="promptEndpoint" value="${escapeAttr(prompt.endpoint)}" disabled>
        <label>Version</label><input id="promptVersion" value="${escapeAttr(prompt.version)}" disabled>
        <label>Name</label><input id="promptName" value="${escapeAttr(prompt.name)}" ${readonly}>
        <label>Model</label><input id="promptModel" value="${escapeAttr(prompt.model)}" ${readonly}>
        <label>Temperature</label><input id="promptTemperature" type="number" step="0.1" min="0" max="2" value="${prompt.temperature}" ${readonly}>
        <label>System Prompt</label><textarea id="promptSystem" style="min-height:320px" ${readonly}>${escapeHtml(prompt.system_prompt)}</textarea>
        <label>User Template</label><textarea id="promptUserTemplate" style="min-height:90px" ${readonly}>${escapeHtml(prompt.user_template)}</textarea>
        <label>Sample input</label><textarea id="promptSample">The air conditioner in ARC room 205 is making loud noise and the room is too warm.</textarea>
        <label>Environment</label><select id="promptEnv">${envOptions()}</select>
        <div class="row"><button onclick="savePrompt(${prompt.id})" ${readonly}>Save</button><button class="secondary" onclick="createPromptDraft(${prompt.id})">Create Draft from This</button><button class="secondary" onclick="testPrompt(${prompt.id})">Test Draft</button><button class="secondary" onclick="runPromptTestCases(${prompt.id}, '${escapeAttr(prompt.endpoint)}')">Run Test Cases Against This Prompt</button><button class="secondary" onclick="runPromptSuites(${prompt.id}, '${escapeAttr(prompt.endpoint)}', true)">Run Required Test Suites Against This Prompt</button><button class="secondary" onclick="runPromptSuites(${prompt.id}, '${escapeAttr(prompt.endpoint)}', false)">Run All Test Suites Against This Prompt</button><button class="secondary" onclick="comparePromptAgainstActive(${prompt.id}, '${escapeAttr(prompt.endpoint)}')">Compare Against Active</button><button class="secondary" onclick="comparePromptAgainstAnother(${prompt.id}, '${escapeAttr(prompt.endpoint)}')">Compare Against Another Prompt</button><button class="danger" onclick="archivePrompt(${prompt.id})">Archive</button></div>
        <div class="ai-panel stack">
          <h3>Promotion Readiness</h3>
          <div class="muted">Activation requires a completed comparison against the current active prompt with no regressions or errors.</div>
          <label>Selected comparison</label><input id="promotionComparisonId" placeholder="cmp_..." value="">
          <label>Override reason</label><textarea id="promotionOverrideReason" placeholder="Required only for Override and Activate"></textarea>
          <div class="button-grid"><button class="secondary" onclick="checkPromotionGate(${prompt.id})">Check Promotion Gate</button><button onclick="activatePrompt(${prompt.id}, false)">Activate Prompt</button><button class="danger" onclick="activatePrompt(${prompt.id}, true)">Override and Activate</button></div>
          <div id="promotionGateResult" class="readiness warn"><strong>Gate status</strong><div class="muted">Select or enter a comparison id, then check readiness.</div></div>
        </div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Prompt test output</strong>${outputToolbar("promptResult")}</div><pre id="promptResult" style="min-height:160px">{}</pre></div>`;
    }

    async function savePrompt(id) {
      await api(`/api/admin/prompt-versions/${id}`, { method: "PATCH", body: JSON.stringify({ name: $("promptName").value, system_prompt: $("promptSystem").value, user_template: $("promptUserTemplate").value, model: $("promptModel").value, temperature: Number($("promptTemperature").value) }) });
      prompts();
    }

    async function createPromptDraft(id) {
      const existing = await api("/api/admin/prompt-versions");
      const selectedPrompt = existing.find(p => p.id === id);
      if (!selectedPrompt) return;
      const version = window.prompt("Draft version", `v${Date.now()}`);
      if (!version) return;
      await api("/api/admin/prompt-versions", { method: "POST", body: JSON.stringify({ endpoint: selectedPrompt.endpoint, version, name: `${selectedPrompt.name} draft`, status: "draft", system_prompt: selectedPrompt.system_prompt, user_template: selectedPrompt.user_template, model: selectedPrompt.model, temperature: selectedPrompt.temperature }) });
      prompts();
    }

    async function testPrompt(id) {
      const data = await api(`/api/admin/prompt-versions/${id}/test`, { method: "POST", body: JSON.stringify({ text: $("promptSample").value, environment_code: $("promptEnv").value }) });
      setConsoleOutput("promptResult", data);
    }

    async function runPromptTestCases(promptId, endpoint) {
      const data = await api("/api/admin/test-cases/run-batch", { method: "POST", body: JSON.stringify({ endpoint, enabled_only: true, prompt_id: promptId }) });
      setConsoleOutput("promptResult", data);
    }

    async function runPromptSuites(promptId, endpoint, requiredOnly) {
      const data = await api("/api/admin/test-suites/run-batch", { method: "POST", body: JSON.stringify({ endpoint, prompt_id: promptId, required_only: requiredOnly, enabled_only: true }) });
      setConsoleOutput("promptResult", data);
    }

    async function comparePromptAgainstActive(candidatePromptId, endpoint) {
      const prompts = await api(`/api/admin/prompt-versions/${endpoint}`);
      const active = prompts.find(p => p.status === "active");
      if (!active) { alert("No active prompt found for this endpoint."); return; }
      await runPromptComparison(active.id, candidatePromptId, endpoint);
    }

    async function comparePromptAgainstAnother(baselinePromptId, endpoint) {
      const other = window.prompt("Candidate prompt id");
      if (!other) return;
      await runPromptComparison(baselinePromptId, Number(other), endpoint);
    }

    async function runPromptComparison(baselinePromptId, candidatePromptId, endpoint) {
      const env = $("promptEnv")?.value || "";
      const data = await api("/api/admin/prompt-comparisons", { method: "POST", body: JSON.stringify({ endpoint, environment_code: env || null, baseline_prompt_id: baselinePromptId, candidate_prompt_id: candidatePromptId, enabled_only: true }) });
      setConsoleOutput("promptResult", data);
      await refreshPromptComparisons();
      renderPromptComparisonDetail(data);
    }

    async function refreshPromptComparisons() {
      if (!$("promptComparisons")) return;
      const comparisons = await api("/api/admin/prompt-comparisons?limit=25").catch(() => []);
      $("promptComparisons").innerHTML = renderPromptComparisonsTable(comparisons);
    }

    function renderPromptComparisonsTable(rows) {
      if (!rows.length) return '<p class="muted">No prompt comparisons yet.</p>';
      return `<table><thead><tr><th>Comparison</th><th>Endpoint</th><th>Environment</th><th>Baseline</th><th>Candidate</th><th>Total</th><th>Improved</th><th>Regressed</th><th>Status</th><th>Started</th><th>Actions</th></tr></thead><tbody>${rows.map(r => {
        const s = r.summary_json || {};
        return `<tr><td><strong>${escapeHtml(r.comparison_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.baseline_version || String(r.baseline_prompt_id))}</td><td>${escapeHtml(r.candidate_version || String(r.candidate_prompt_id))}</td><td>${s.total ?? 0}</td><td>${s.improved ?? 0}</td><td>${s.regressed ?? 0}</td><td><span class="pill ${r.status === "completed" ? "ok" : r.status === "failed" ? "danger" : "warning"}">${escapeHtml(r.status)}</span></td><td>${escapeHtml(r.started_at || "")}</td><td><button class="secondary" onclick="viewPromptComparison('${escapeAttr(r.comparison_id)}')">View</button></td></tr>`;
      }).join("")}</tbody></table>`;
    }

    async function viewPromptComparison(comparisonId) {
      const data = await api(`/api/admin/prompt-comparisons/${comparisonId}`);
      renderPromptComparisonDetail(data);
    }

    function renderPromptComparisonDetail(data) {
      const target = $("promptComparisonDetail");
      if (!target) return;
      const summary = data.summary || data.summary_json || {};
      const cases = data.cases || [];
      target.innerHTML = `<div class="row" style="margin-bottom:10px"><button class="secondary" onclick="useComparisonForPromotion('${escapeAttr(data.comparison_id)}', ${Number(data.candidate_prompt_id || 0)})">Use This Comparison for Promotion</button><span class="muted">Candidate prompt #${escapeHtml(data.candidate_prompt_id || "")}</span></div><div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.total ?? 0}</div><div class="muted">Total</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.improved ?? 0}</div><div class="muted">Improved</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.regressed ?? 0}</div><div class="muted">Regressed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.error ?? 0}</div><div class="muted">Errors</div></div></div>
      </div>
      <table><thead><tr><th>Test Case</th><th>Baseline</th><th>Candidate</th><th>Result</th><th>Duration</th><th>Actions</th></tr></thead><tbody>${cases.map(c => {
        const details = c.comparison_json || c;
        const baseline = details.baseline || {};
        const candidate = details.candidate || {};
        return `<tr><td>${escapeHtml(details.test_case_name || c.test_case_name || String(c.test_case_id))}</td><td><span class="pill ${baseline.status === "passed" || baseline.status === "warning" ? "ok" : "danger"}">${escapeHtml(baseline.status || c.baseline_status || "")}</span></td><td><span class="pill ${candidate.status === "passed" || candidate.status === "warning" ? "ok" : "danger"}">${escapeHtml(candidate.status || c.candidate_status || "")}</span></td><td><span class="pill ${details.result === "regressed" || details.result === "error" ? "danger" : details.result === "improved" ? "ok" : ""}">${escapeHtml(details.result || c.result || "")}</span></td><td>${baseline.duration_ms ?? ""} / ${candidate.duration_ms ?? ""} ms</td><td class="row">${baseline.run_id ? `<button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(baseline.run_id)}')">Baseline Trace</button>` : ""}${candidate.run_id ? `<button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(candidate.run_id)}')">Candidate Trace</button>` : ""}</td></tr>`;
      }).join("")}</tbody></table>`;
    }

    function useComparisonForPromotion(comparisonId, candidatePromptId) {
      if ($("promotionComparisonId")) {
        $("promotionComparisonId").value = comparisonId;
        checkPromotionGate(candidatePromptId);
      } else {
        alert(`Open candidate prompt #${candidatePromptId}, then use comparison ${comparisonId} for promotion.`);
      }
    }

    function renderGateResult(data) {
      const target = $("promotionGateResult");
      if (!target) return;
      const summary = data.summary || {};
      const suite = data.suite_readiness || {};
      target.className = `readiness ${data.allowed ? "" : "fail"}`;
      target.innerHTML = `<strong>${data.allowed ? "Gate passed" : data.gate_status === "overridden" ? "Gate overridden" : "Gate blocked"}</strong>
        <div class="muted">Comparison: ${escapeHtml(data.comparison_id || "")}</div>
        ${data.reasons?.length ? `<ul>${data.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : '<p class="muted">No blocking reasons.</p>'}
        <div class="result-grid">
          <div>Total: <strong>${summary.total ?? 0}</strong></div><div>Baseline passed: <strong>${summary.baseline_passed ?? 0}</strong></div><div>Candidate passed: <strong>${summary.candidate_passed ?? 0}</strong></div>
          <div>Improved: <strong>${summary.improved ?? 0}</strong></div><div>Regressed: <strong>${summary.regressed ?? 0}</strong></div><div>Error: <strong>${summary.error ?? 0}</strong></div>
        </div>
        <h3>Required Suite Readiness</h3>
        <div class="pill ${suite.required_suites_found ? (suite.required_suites_passed ? "ok" : "danger") : ""}">${suite.required_suites_found ? (suite.required_suites_passed ? "required suites passed" : "required suites blocked") : "no required suites"}</div>
        ${suite.suite_failures?.length ? `<ul>${suite.suite_failures.map(f => `<li>${escapeHtml(f.name || f.suite_id)}: ${escapeHtml(f.reason)}</li>`).join("")}</ul>` : '<p class="muted">No required suite failures.</p>'}`;
    }

    async function checkPromotionGate(id) {
      const comparisonId = $("promotionComparisonId")?.value || "";
      const data = await api(`/api/admin/prompt-versions/${id}/promotion-check`, { method: "POST", body: JSON.stringify({ comparison_id: comparisonId || null }) });
      renderGateResult(data);
      return data;
    }

    async function activatePrompt(id, override = false) {
      const body = { comparison_id: $("promotionComparisonId")?.value || null, override, override_reason: $("promotionOverrideReason")?.value || "" };
      try {
        const data = await api(`/api/admin/prompt-versions/${id}/activate`, { method: "POST", body: JSON.stringify(body) });
        renderGateResult(data.gate || { allowed: true, summary: {}, reasons: [], comparison_id: body.comparison_id });
        await refreshPromptPromotions();
        prompts();
      } catch (e) {
        const detail = e.data?.detail;
        renderGateResult(typeof detail === "object" ? detail : { allowed: false, gate_status: "blocked", reasons: [e.message], summary: {}, comparison_id: body.comparison_id });
      }
    }

    async function refreshPromptPromotions() {
      if (!$("promptPromotions")) return;
      const promotions = await api("/api/admin/prompt-promotions?limit=25").catch(() => []);
      $("promptPromotions").innerHTML = renderPromptPromotionsTable(promotions);
    }

    function renderPromptPromotionsTable(rows) {
      if (!rows.length) return '<p class="muted">No prompt promotions recorded yet.</p>';
      return `<table><thead><tr><th>Promotion</th><th>Endpoint</th><th>Previous</th><th>Promoted</th><th>Comparison</th><th>Gate</th><th>Override</th><th>By</th><th>At</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `<tr>
        <td><strong>${escapeHtml(r.promotion_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.previous_version || String(r.previous_prompt_id || ""))}</td><td>${escapeHtml(r.promoted_version || String(r.promoted_prompt_id))}</td><td>${escapeHtml(r.comparison_id || "")}</td>
        <td><span class="pill ${r.gate_status === "passed" ? "ok" : r.gate_status === "overridden" ? "warning" : "danger"}">${escapeHtml(r.gate_status)}</span></td><td>${r.override_used ? "Yes" : "No"}</td><td>${escapeHtml(r.promoted_by_username || "")}</td><td>${escapeHtml(r.promoted_at || "")}</td>
        <td><button class="secondary" onclick="viewPromptPromotion('${escapeAttr(r.promotion_id)}')">View</button></td>
      </tr>`).join("")}</tbody></table>`;
    }

    async function viewPromptPromotion(promotionId) {
      const data = await api(`/api/admin/prompt-promotions/${promotionId}`);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="promotionModal"><div class="modal" style="max-width:900px"><h2>Prompt Promotion</h2><div class="modal-body">
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Promotion JSON</strong>${outputToolbar("promotionOut")}</div><pre id="promotionOut" style="min-height:320px"></pre></div>
      </div><div class="modal-actions"><button class="secondary" onclick="$('promotionModal').remove()">Close</button></div></div></div>`);
      setConsoleOutput("promotionOut", data);
    }

    async function archivePrompt(id) {
      if (!confirm("Archive this prompt version?")) return;
      await api(`/api/admin/prompt-versions/${id}/archive`, { method: "POST" });
      prompts();
    }

    async function keys() {
      const data = await api("/api/admin/api-keys");
      pageShell("API Keys", `<div class="grid">
        <div class="card span-4"><h2>Generate key</h2><div class="card-body stack"><label>Name</label><input id="kName" value="external-tester"><button onclick="createKey()">Generate</button></div></div>
        <div class="card span-8"><h2>Keys</h2><div class="card-body">${table(data, ["key_id","name","enabled","usage_count","last_used_at"], "disableKey")}</div></div>
        <div class="card span-12"><h2>Generated key output</h2><pre id="kOut">{}</pre></div>
      </div>`);
    }
    async function createKey() { const data = await api("/api/admin/api-keys", { method: "POST", body: JSON.stringify({ name: $("kName").value }) }); $("kOut").textContent = JSON.stringify(data, null, 2); }
    async function disableKey(id) { await api(`/api/admin/api-keys/${id}`, { method: "PATCH", body: JSON.stringify({ enabled: false }) }); keys(); }
    async function users() {
      const data = await api("/api/admin/users");
      pageShell("Users", `<div class="grid">
        <div class="card span-4"><h2>Create user</h2><div class="card-body stack"><label>Username</label><input id="uName"><label>Password</label><input id="uPass" type="password"><label>Role</label><select id="uRole"><option>user</option><option>admin</option></select><button onclick="createUser()">Create</button></div></div>
        <div class="card span-8"><h2>Users</h2><div class="card-body">${table(data, ["user_id","username","role","enabled","last_login_at"])}</div></div>
      </div>`);
    }
    async function createUser() { await api("/api/admin/users", { method: "POST", body: JSON.stringify({ username: $("uName").value, password: $("uPass").value, role: $("uRole").value }) }); users(); }
    async function logs() {
      const data = await api("/api/admin/logs?lines=220");
      const runs = await api("/api/admin/workflow-runs?limit=25").catch(() => []);
      pageShell("Logs", `<div class="grid">
        <div class="card span-12"><h2>Workflow Runs</h2><div class="card-body">${renderWorkflowRunsTable(runs)}</div></div>
        <div class="card span-12"><h2>Trace Detail</h2><div class="card-body" id="logTraceDetail"><span class="muted">Select View Trace from a workflow run.</span></div></div>
        <div class="card span-12"><h2>Runtime log</h2><pre>${data.lines.join("\n")}</pre></div>
      </div>`);
    }

    function renderWorkflowRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No workflow runs recorded yet.</p>';
      return `<table><thead><tr><th>Run ID</th><th>Endpoint</th><th>Environment</th><th>Status</th><th>Duration</th><th>Started</th><th>Source</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr><td><strong>${escapeHtml(r.run_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td><span class="pill ${r.status === "failed" ? "danger" : r.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(r.status)}</span></td><td>${r.duration_ms ?? ""} ms</td><td>${escapeHtml(r.started_at || "")}</td><td>${escapeHtml(r.source || "")}</td><td><button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(r.run_id)}')">View Trace</button></td></tr>`).join("")}</tbody></table>`;
    }

    async function viewWorkflowTrace(runId) {
      const trace = await api(`/api/admin/workflow-runs/${runId}`);
      $("logTraceDetail").innerHTML = renderWorkflowTrace(trace);
    }
    async function reports() { const data = await api("/api/admin/reports/usage"); pageShell("Reports", `<div class="card"><h2>Usage</h2><div class="card-body">${table(data, ["endpoint","status_code","key_name","environment_code","calls","avg_duration_ms"])}</div></div>`); }
    async function kb() { const data = await api("/api/kb/status"); pageShell("Knowledge Base", `<div class="card"><h2>Future KB interface</h2><div class="card-body"><pre>${JSON.stringify(data, null, 2)}</pre></div></div>`); }
    async function remote() { const data = await api("/api/admin/settings/remote_access_url").catch(()=>({ value:"" })); pageShell("Remote Access", `<div class="card"><h2>Remote link notes</h2><div class="card-body stack"><input id="remoteUrl" value="${data.value||""}" placeholder="https://example.trycloudflare.com"><button onclick="saveRemote()">Save</button><p class="muted">Cloudflare is still started manually. Store the URL here for reference.</p></div></div>`); }
    async function saveRemote() { await api("/api/admin/settings/remote_access_url", { method: "PATCH", body: JSON.stringify({ value: $("remoteUrl").value }) }); remote(); }
    async function system() {
      const s = await api("/api/system/status");
      pageShell("System", `<div class="grid"><div class="card span-6"><h2>Status</h2><div class="card-body"><pre>${JSON.stringify(s, null, 2)}</pre></div></div>
      <div class="card span-6"><h2>Local-only controls</h2><div class="card-body row"><button onclick="api('/api/system/ollama/start',{method:'POST'}).then(system)">Start Ollama</button><button class="secondary" onclick="api('/api/system/ollama/stop',{method:'POST'}).then(system)">Stop Ollama</button><button class="danger" onclick="api('/api/system/shutdown',{method:'POST'})">Stop API</button></div></div></div>`);
    }
    function table(rows, cols, action) {
      if (!rows || !rows.length) return "<p class='muted'>No records.</p>";
      return `<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join("")}${action?"<th>Action</th>":""}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${r[c] ?? ""}</td>`).join("")}${action?`<td><button class="danger" onclick="${action}('${r.key_id}')">Disable</button></td>`:""}</tr>`).join("")}</tbody></table>`;
    }
    boot();
  </script>
</body>
</html>"""


@app.get("/ui", response_class=HTMLResponse)
async def ui() -> HTMLResponse:
    return HTMLResponse(PORTAL_HTML)


@app.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    check_login_rate_limit(request, payload.username)
    if payload.password.strip() in DISALLOWED_ADMIN_PASSWORDS:
        record_login_failure(request, payload.username)
        raise HTTPException(status_code=403, detail="Default or weak password is not allowed")
    row = db_fetchone("SELECT * FROM users WHERE username = ?", (payload.username.strip(),))
    if not row or not row["enabled"] or not verify_password(payload.password, row["password_hash"]):
        record_login_failure(request, payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if password_needs_rehash(row["password_hash"]):
        db_execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (hash_password(payload.password), row["user_id"]))
    clear_login_failures(request, payload.username)
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    db_execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (hash_text(token), row["user_id"], now_text(), expires_at),
    )
    db_execute("UPDATE users SET last_login_at = ? WHERE user_id = ?", (now_text(), row["user_id"]))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
        max_age=SESSION_TTL_SECONDS,
    )
    return {"status": "ok", "user": {"username": row["username"], "role": row["role"]}}


@app.post("/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db_execute("DELETE FROM sessions WHERE token_hash = ?", (hash_text(token),))
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return user.model_dump()


@app.get("/api/default-api-key")
async def default_api_key(user: PortalUser = Depends(current_user)) -> dict[str, str]:
    return {"api_key": os.getenv("LLM_API_KEY", "my-secret-key")}


@app.get("/api/environments")
async def list_environments(user: PortalUser = Depends(current_user)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM environments ORDER BY environment_code")
    return [dict(row) for row in rows]


@app.post("/api/admin/environments")
async def create_environment(payload: EnvironmentRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    timestamp = now_text()
    db_execute(
        """
        INSERT INTO environments (environment_code, name, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(environment_code) DO UPDATE SET name = excluded.name, enabled = excluded.enabled, updated_at = excluded.updated_at
        """,
        (payload.environment_code.upper(), payload.name, 1 if payload.enabled else 0, timestamp, timestamp),
    )
    ensure_validation_rules(payload.environment_code.upper())
    return {"status": "ok", "environment_code": payload.environment_code.upper()}


@app.patch("/api/admin/environments/{environment_code}")
async def patch_environment(environment_code: str, payload: EnvironmentPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM environments WHERE environment_code = ?", (environment_code.upper(),))
    if not row:
        raise HTTPException(status_code=404, detail="Environment not found")
    db_execute(
        "UPDATE environments SET name = ?, enabled = ?, updated_at = ? WHERE environment_code = ?",
        (
            payload.name if payload.name is not None else row["name"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            now_text(),
            environment_code.upper(),
        ),
    )
    return {"status": "ok"}


@app.get("/api/admin/environments/{environment_code}/codes")
async def list_codes(environment_code: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    values = get_environment_values(environment_code.upper())
    rows = db_fetchall(
        """
        SELECT code_id, environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at
        FROM code_values
        WHERE environment_code = ?
        ORDER BY category, code
        """,
        (environment_code.upper(),),
    )
    return {"environment_code": environment_code.upper(), "categories": values, "rows": [dict(row) for row in rows]}


@app.post("/api/admin/environments/{environment_code}/codes/preview")
async def preview_codes(environment_code: str, payload: CodeImportRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return preview_code_import(environment_code.upper(), payload.category, payload.text or "\n".join(payload.values or []))


@app.post("/api/admin/environments/{environment_code}/codes/import")
async def import_codes(environment_code: str, payload: CodeImportRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    rows = parse_code_rows(payload.text or "\n".join(payload.values or []))
    count = import_code_rows(environment_code.upper(), payload.category, rows, payload.replace)
    return {"status": "ok", "environment_code": environment_code.upper(), "category": payload.category, "count": count}


@app.patch("/api/admin/environments/{environment_code}/codes/{code_id}")
async def patch_code_value(
    environment_code: str,
    code_id: int,
    payload: CodeValuePatchRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    row = db_fetchone(
        "SELECT * FROM code_values WHERE environment_code = ? AND code_id = ?",
        (environment_code.upper(), code_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Code value not found")
    metadata = payload.metadata_json if payload.metadata_json is not None else row["metadata_json"]
    if metadata:
        try:
            json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON") from exc
    db_execute(
        """
        UPDATE code_values
        SET code = ?, label = ?, aliases = ?, metadata_json = ?, enabled = ?, source = 'Manual', updated_at = ?
        WHERE code_id = ? AND environment_code = ?
        """,
        (
            payload.code.strip() if payload.code else row["code"],
            payload.label if payload.label is not None else row["label"],
            payload.aliases if payload.aliases is not None else row["aliases"],
            metadata,
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            now_text(),
            code_id,
            environment_code.upper(),
        ),
    )
    return {"status": "ok", "code_id": code_id}


@app.get("/api/environments/{environment_code}/validation-rules")
async def list_validation_rules(environment_code: str, user: PortalUser = Depends(current_user)) -> list[dict[str, Any]]:
    return get_validation_rules(environment_code.upper())


@app.patch("/api/admin/environments/{environment_code}/validation-rules/{rule_id}")
async def patch_validation_rule(
    environment_code: str,
    rule_id: int,
    payload: ValidationRulePatchRequest,
    user: PortalUser = Depends(current_admin),
) -> dict[str, Any]:
    row = db_fetchone(
        "SELECT * FROM environment_validation_rules WHERE environment_code = ? AND id = ?",
        (environment_code.upper(), rule_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Validation rule not found")
    category = payload.code_category if payload.code_category is not None else row["code_category"]
    if category and category not in CODE_CATEGORIES and not category.startswith("custom:"):
        raise HTTPException(status_code=400, detail="Invalid code category")
    db_execute(
        """
        UPDATE environment_validation_rules
        SET enabled = ?, required = ?, code_category = ?, must_match_code_list = ?,
            allow_unknown = ?, severity = ?, updated_at = ?
        WHERE environment_code = ? AND id = ?
        """,
        (
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            1 if (payload.required if payload.required is not None else bool(row["required"])) else 0,
            category,
            1 if (payload.must_match_code_list if payload.must_match_code_list is not None else bool(row["must_match_code_list"])) else 0,
            1 if (payload.allow_unknown if payload.allow_unknown is not None else bool(row["allow_unknown"])) else 0,
            payload.severity if payload.severity is not None else row["severity"],
            now_text(),
            environment_code.upper(),
            rule_id,
        ),
    )
    return {"status": "ok", "rule_id": rule_id}


@app.post("/api/admin/environments/{environment_code}/validation-rules/reset-defaults")
async def reset_environment_validation_rules(environment_code: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    reset_validation_rules(environment_code.upper())
    return {"status": "ok", "environment_code": environment_code.upper()}


@app.post("/api/environments/{environment_code}/validate-sample")
async def validate_sample(environment_code: str, payload: ValidateSampleRequest, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return validate_ai_output(environment_code.upper(), payload.values or {})


@app.get("/api/admin/users")
async def list_users(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT user_id, username, role, enabled, created_at, last_login_at FROM users ORDER BY username")
    return [dict(row) for row in rows]


@app.post("/api/admin/users")
async def create_user(payload: UserCreateRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    try:
        db_execute(
            "INSERT INTO users (username, password_hash, role, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
            (payload.username.strip(), hash_password(payload.password), payload.role, now_text()),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Username already exists") from exc
    return {"status": "ok", "username": payload.username.strip()}


@app.patch("/api/admin/users/{user_id}")
async def patch_user(user_id: int, payload: UserPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    db_execute(
        "UPDATE users SET password_hash = ?, role = ?, enabled = ? WHERE user_id = ?",
        (
            hash_password(payload.password) if payload.password else row["password_hash"],
            payload.role if payload.role else row["role"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            user_id,
        ),
    )
    return {"status": "ok"}


@app.get("/api/output-contracts/{endpoint}")
async def read_output_contract(endpoint: str, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    row = active_contract(endpoint)
    if not row:
        raise HTTPException(status_code=404, detail="No active contract found")
    result = dict(row)
    result["schema_json"] = json.loads(result["schema_json"])
    return result


@app.get("/api/prompt-versions/active/{endpoint}")
async def read_active_prompt_info(endpoint: str, user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    row = active_prompt_version(endpoint)
    return {
        "endpoint": row["endpoint"],
        "version": row["version"],
        "name": row["name"],
        "status": row["status"],
        "model": row["model"],
        "temperature": row["temperature"],
        "updated_at": row["updated_at"],
    }


@app.get("/api/admin/output-contracts")
async def list_output_contracts(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_output_contracts ORDER BY endpoint, updated_at DESC")
    result = []
    for row in rows:
        item = dict(row)
        item["schema_json"] = json.loads(item["schema_json"])
        result.append(item)
    return result


@app.get("/api/admin/output-contracts/{endpoint}")
async def list_output_contracts_for_endpoint(endpoint: str, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_output_contracts WHERE endpoint = ? ORDER BY updated_at DESC", (endpoint,))
    result = []
    for row in rows:
        item = dict(row)
        item["schema_json"] = json.loads(item["schema_json"])
        result.append(item)
    return result


@app.post("/api/admin/output-contracts")
async def create_output_contract(payload: OutputContractRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    timestamp = now_text()
    if payload.status == "active":
        db_execute("UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, payload.endpoint))
    try:
        db_execute(
            """
            INSERT INTO ai_output_contracts
            (endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.endpoint,
                payload.version,
                payload.name,
                payload.status,
                json.dumps(payload.schema_def),
                1 if payload.strict_mode else 0,
                timestamp,
                timestamp,
                user.user_id,
                user.user_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Contract endpoint/version already exists") from exc
    row = db_fetchone("SELECT id FROM ai_output_contracts WHERE endpoint = ? AND version = ?", (payload.endpoint, payload.version))
    return {"status": "ok", "contract_id": row["id"] if row else None}


@app.patch("/api/admin/output-contracts/{contract_id}")
async def patch_output_contract(contract_id: int, payload: OutputContractPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_output_contracts WHERE id = ?", (contract_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    timestamp = now_text()
    new_status = payload.status if payload.status is not None else row["status"]
    if new_status == "active" and row["status"] != "active":
        db_execute("UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, row["endpoint"]))
    db_execute(
        """
        UPDATE ai_output_contracts
        SET name = ?, status = ?, schema_json = ?, strict_mode = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            new_status,
            json.dumps(payload.schema_def) if payload.schema_def is not None else row["schema_json"],
            1 if (payload.strict_mode if payload.strict_mode is not None else bool(row["strict_mode"])) else 0,
            timestamp,
            user.user_id,
            contract_id,
        ),
    )
    return {"status": "ok", "contract_id": contract_id}


@app.post("/api/admin/output-contracts/{contract_id}/activate")
async def activate_output_contract(contract_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_output_contracts WHERE id = ?", (contract_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    timestamp = now_text()
    db_execute("UPDATE ai_output_contracts SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, row["endpoint"]))
    db_execute("UPDATE ai_output_contracts SET status = 'active', updated_at = ?, updated_by = ? WHERE id = ?", (timestamp, user.user_id, contract_id))
    return {"status": "ok", "contract_id": contract_id}


@app.post("/api/admin/output-contracts/{contract_id}/validate-sample")
async def validate_contract_sample(contract_id: int, payload: ValidateSampleRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_output_contracts WHERE id = ?", (contract_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    schema = json.loads(row["schema_json"])
    pseudo_endpoint = f"__contract_test_{contract_id}"
    timestamp = now_text()
    db_execute(
        """
        INSERT OR REPLACE INTO ai_output_contracts
        (id, endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (-contract_id, pseudo_endpoint, row["version"], row["name"], json.dumps(schema), row["strict_mode"], timestamp, timestamp),
    )
    result = validate_output_contract(pseudo_endpoint, payload.values or {})
    db_execute("DELETE FROM ai_output_contracts WHERE id = ?", (-contract_id,))
    return result


@app.get("/api/admin/prompt-versions")
async def list_prompt_versions(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_prompt_versions ORDER BY endpoint, updated_at DESC")
    return [dict(row) for row in rows]


@app.get("/api/admin/prompt-versions/{endpoint}")
async def list_prompt_versions_for_endpoint(endpoint: str, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT * FROM ai_prompt_versions WHERE endpoint = ? ORDER BY updated_at DESC", (endpoint,))
    return [dict(row) for row in rows]


@app.post("/api/admin/prompt-versions")
async def create_prompt_version(payload: PromptVersionRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    if payload.endpoint not in SUPPORTED_PROMPT_ENDPOINTS:
        raise HTTPException(status_code=400, detail="Unsupported prompt endpoint")
    if payload.status == "active":
        raise HTTPException(status_code=400, detail="Create prompt versions as draft, then use the promotion gate to activate")
    timestamp = now_text()
    try:
        db_execute(
            """
            INSERT INTO ai_prompt_versions
            (endpoint, version, name, status, system_prompt, user_template, model, temperature, created_at, updated_at, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.endpoint,
                payload.version,
                payload.name,
                payload.status,
                payload.system_prompt,
                payload.user_template,
                payload.model,
                payload.temperature,
                timestamp,
                timestamp,
                user.user_id,
                user.user_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Prompt endpoint/version already exists") from exc
    row = db_fetchone("SELECT id FROM ai_prompt_versions WHERE endpoint = ? AND version = ?", (payload.endpoint, payload.version))
    return {"status": "ok", "prompt_id": row["id"] if row else None}


@app.patch("/api/admin/prompt-versions/{prompt_id}")
async def patch_prompt_version(prompt_id: int, payload: PromptVersionPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    if row["status"] == "archived":
        raise HTTPException(status_code=400, detail="Archived prompts cannot be edited")
    db_execute(
        """
        UPDATE ai_prompt_versions
        SET name = ?, system_prompt = ?, user_template = ?, model = ?, temperature = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            payload.system_prompt if payload.system_prompt is not None else row["system_prompt"],
            payload.user_template if payload.user_template is not None else row["user_template"],
            payload.model if payload.model is not None else row["model"],
            payload.temperature if payload.temperature is not None else row["temperature"],
            now_text(),
            user.user_id,
            prompt_id,
        ),
    )
    return {"status": "ok", "prompt_id": prompt_id}


@app.post("/api/admin/prompt-versions/{prompt_id}/promotion-check")
async def prompt_promotion_check(prompt_id: int, payload: PromotionCheckRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return check_prompt_promotion_gate(prompt_id, payload.comparison_id if payload else None)


@app.post("/api/admin/prompt-versions/{prompt_id}/activate")
async def activate_prompt_version(prompt_id: int, payload: PromptActivationRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    if row["status"] == "archived":
        raise HTTPException(status_code=400, detail="Archived prompts cannot be activated")
    activation = payload or PromptActivationRequest()
    gate = check_prompt_promotion_gate(prompt_id, activation.comparison_id)
    gate_status = gate["gate_status"]
    override_used = False
    override_reason = None
    if not gate["allowed"]:
        if not activation.override:
            raise HTTPException(status_code=409, detail=gate)
        override_reason = (activation.override_reason or "").strip()
        if not override_reason:
            raise HTTPException(status_code=400, detail="override_reason is required when override is true")
        gate_status = "overridden"
        override_used = True
    timestamp = now_text()
    previous = active_prompt_for_endpoint(row["endpoint"])
    previous_prompt_id = previous["id"] if previous else None
    db_execute("UPDATE ai_prompt_versions SET status = 'archived', updated_at = ? WHERE endpoint = ? AND status = 'active'", (timestamp, row["endpoint"]))
    db_execute("UPDATE ai_prompt_versions SET status = 'active', updated_at = ?, updated_by = ? WHERE id = ?", (timestamp, user.user_id, prompt_id))
    promotion_id = record_prompt_promotion(
        row["endpoint"],
        previous_prompt_id,
        prompt_id,
        activation.comparison_id,
        gate_status,
        override_used,
        override_reason,
        user.user_id,
        gate.get("summary") or {},
    )
    return {"status": "ok", "prompt_id": prompt_id, "promotion_id": promotion_id, "gate": gate | {"gate_status": gate_status, "override_used": override_used}}


@app.post("/api/admin/prompt-versions/{prompt_id}/archive")
async def archive_prompt_version(prompt_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    if row["status"] == "active":
        active_count = db_fetchone("SELECT COUNT(*) AS count FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active'", (row["endpoint"],))
        if active_count and active_count["count"] <= 1:
            raise HTTPException(status_code=400, detail="Cannot archive the only active prompt for an endpoint")
    db_execute("UPDATE ai_prompt_versions SET status = 'archived', updated_at = ?, updated_by = ? WHERE id = ?", (now_text(), user.user_id, prompt_id))
    return {"status": "ok", "prompt_id": prompt_id}


@app.post("/api/admin/prompt-versions/{prompt_id}/test")
async def test_prompt_version(prompt_id: int, payload: PromptTestRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_prompt_versions WHERE id = ?", (prompt_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    values = get_environment_values(payload.environment_code) if payload.environment_code else {"buildings": [], "priorities": ["NORMAL"]}
    context = {
        "text": payload.text,
        "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
        "valid_buildings": values.get("buildings") or [],
        "valid_priorities": values.get("priorities") or ["NORMAL"],
    }
    endpoint = row["endpoint"]
    if endpoint == "cmms-intake":
        try:
            parts = json.loads(row["system_prompt"])
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Prompt system_prompt must be JSON for cmms-intake") from exc
        messages = [{"role": "system", "content": render_prompt_template(parts.get("field_extractor", ""), context)}, {"role": "user", "content": render_prompt_template(row["user_template"], context)}]
    else:
        messages = [{"role": "system", "content": render_prompt_template(row["system_prompt"], context)}, {"role": "user", "content": render_prompt_template(row["user_template"], context)}]
    output = await call_ollama(messages, temperature=float(row["temperature"]), model=row["model"])
    return {
        "status": "ok",
        "prompt_id": prompt_id,
        "endpoint": endpoint,
        "version": row["version"],
        "model": row["model"],
        "temperature": row["temperature"],
        "output": output,
    }


@app.get("/api/admin/test-cases")
async def list_test_cases(
    endpoint: str | None = None,
    environment_code: str | None = None,
    enabled: bool | None = None,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("endpoint = ?")
        params.append(endpoint)
    if environment_code:
        filters.append("environment_code = ?")
        params.append(environment_code.upper())
    if enabled is not None:
        filters.append("enabled = ?")
        params.append(1 if enabled else 0)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_cases {where} ORDER BY updated_at DESC, id DESC", tuple(params))
    result = []
    for row in rows:
        item = dict(row)
        item["expected_json"] = json.loads(item["expected_json"]) if item.get("expected_json") else None
        result.append(item)
    return result


@app.post("/api/admin/test-cases")
async def create_test_case(payload: TestCaseRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    timestamp = now_text()
    with DB_LOCK:
        with db_connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_test_cases
                (name, endpoint, environment_code, input_text, source, expected_json, enabled, tags, notes, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.endpoint,
                    payload.environment_code.upper() if payload.environment_code else None,
                    payload.input_text,
                    payload.source or "manual",
                    safe_json(payload.expected_json),
                    1 if payload.enabled else 0,
                    payload.tags,
                    payload.notes,
                    timestamp,
                    timestamp,
                    user.user_id,
                    user.user_id,
                ),
            )
            conn.commit()
            return {"status": "ok", "test_case_id": int(cursor.lastrowid)}


@app.get("/api/admin/test-cases/{test_case_id}")
async def get_test_case(test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_test_cases WHERE id = ?", (test_case_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")
    item = dict(row)
    item["expected_json"] = json.loads(item["expected_json"]) if item.get("expected_json") else None
    return item


@app.patch("/api/admin/test-cases/{test_case_id}")
async def patch_test_case(test_case_id: int, payload: TestCasePatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_test_cases WHERE id = ?", (test_case_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")
    endpoint = payload.endpoint if payload.endpoint is not None else row["endpoint"]
    environment_code = payload.environment_code.upper() if payload.environment_code is not None and payload.environment_code else (None if payload.environment_code == "" else row["environment_code"])
    db_execute(
        """
        UPDATE ai_test_cases
        SET name = ?, endpoint = ?, environment_code = ?, input_text = ?, source = ?, expected_json = ?,
            enabled = ?, tags = ?, notes = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            endpoint,
            environment_code,
            payload.input_text if payload.input_text is not None else row["input_text"],
            payload.source if payload.source is not None else row["source"],
            safe_json(payload.expected_json) if payload.expected_json is not None else row["expected_json"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            payload.tags if payload.tags is not None else row["tags"],
            payload.notes if payload.notes is not None else row["notes"],
            now_text(),
            user.user_id,
            test_case_id,
        ),
    )
    return {"status": "ok", "test_case_id": test_case_id}


@app.delete("/api/admin/test-cases/{test_case_id}")
async def delete_test_case(test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    db_execute("DELETE FROM ai_test_cases WHERE id = ?", (test_case_id,))
    return {"status": "ok", "test_case_id": test_case_id}


async def run_test_case_row(row: sqlite3.Row, prompt_id: int | None = None, environment_override: str | None = None) -> dict[str, Any]:
    started_at = now_text()
    started = parse_timestamp(started_at) or time.time()
    endpoint = row["endpoint"]
    environment_code = environment_override.upper() if environment_override else row["environment_code"]
    prompt_row = prompt_row_for(endpoint, prompt_id) if endpoint in SUPPORTED_PROMPT_ENDPOINTS else None
    try:
        actual = await execute_ai_endpoint_for_test(endpoint, row["input_text"], environment_code, source="test_case", prompt_id=prompt_id)
        comparison = compare_test_case_result(json.loads(row["expected_json"]) if row["expected_json"] else None, actual)
        status = test_case_run_status(comparison)
        if status == "passed" and isinstance(actual.get("ai_validation"), dict) and actual["ai_validation"].get("warnings"):
            status = "warning"
        error_message = None
    except Exception as exc:
        actual = {}
        comparison = {"passed": False, "summary": str(exc), "field_results": [], "contract_result": {}, "environment_result": {}}
        status = "error"
        error_message = str(exc)
    finished_at = now_text()
    finished = parse_timestamp(finished_at) or time.time()
    duration_ms = int(max(0, (finished - started) * 1000))
    run_id = actual.get("run_id") if isinstance(actual, dict) else None
    with DB_LOCK:
        with db_connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_test_case_runs
                (test_case_id, run_id, endpoint, environment_code, prompt_id, prompt_version, status, started_at, finished_at, duration_ms, actual_json, comparison_json, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    run_id,
                    endpoint,
                    environment_code,
                    prompt_row["id"] if prompt_row else None,
                    prompt_row["version"] if prompt_row else None,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    safe_json(actual),
                    safe_json(comparison),
                    error_message,
                ),
            )
            conn.commit()
            run_record_id = int(cursor.lastrowid)
    return {"id": run_record_id, "test_case_id": row["id"], "run_id": run_id, "endpoint": endpoint, "environment_code": environment_code, "prompt_id": prompt_row["id"] if prompt_row else None, "prompt_version": prompt_row["version"] if prompt_row else None, "status": status, "duration_ms": duration_ms, "actual_json": actual, "comparison_json": comparison, "error_message": error_message}


def suite_status_from_summary(summary: dict[str, Any]) -> str:
    if summary["zero_error_required"] and summary["error"] > 0:
        return "error"
    if not summary["meets_pass_rate"]:
        return "failed"
    if summary["failed"] > 0:
        return "failed"
    if summary["warning"] > 0:
        return "warning"
    return "passed"


def suite_summary_from_runs(runs: list[dict[str, Any]], suite: sqlite3.Row) -> dict[str, Any]:
    total = len(runs)
    summary: dict[str, Any] = {
        "total": total,
        "passed": 0,
        "failed": 0,
        "warning": 0,
        "error": 0,
        "pass_rate": 0.0,
        "min_pass_rate": float(suite["min_pass_rate"]),
        "meets_pass_rate": False,
        "zero_error_required": bool(suite["zero_error_required"]),
        "zero_error_met": True,
        "status": "failed",
    }
    for run in runs:
        status = run.get("status") or "error"
        if status in {"passed", "failed", "warning", "error"}:
            summary[status] += 1
        else:
            summary["error"] += 1
    summary["pass_rate"] = round(summary["passed"] / total, 4) if total else 0.0
    summary["meets_pass_rate"] = summary["pass_rate"] >= float(suite["min_pass_rate"])
    summary["zero_error_met"] = summary["error"] == 0
    summary["status"] = suite_status_from_summary(summary)
    return summary


async def run_test_suite_row(suite: sqlite3.Row, prompt_id: int | None = None, environment_override: str | None = None, user_id: int | None = None) -> dict[str, Any]:
    suite_run_id = "suite_run_" + secrets.token_hex(8)
    started_at = now_text()
    started = parse_timestamp(started_at) or time.time()
    endpoint = suite["endpoint"]
    environment_code = environment_override.upper() if environment_override else suite["environment_code"]
    prompt_row = prompt_row_for(endpoint, prompt_id) if endpoint in SUPPORTED_PROMPT_ENDPOINTS else None
    case_rows = db_fetchall(
        """
        SELECT tc.*
        FROM ai_test_suite_cases sc
        JOIN ai_test_cases tc ON tc.id = sc.test_case_id
        WHERE sc.suite_id = ? AND sc.enabled = 1 AND tc.enabled = 1
        ORDER BY sc.sort_order, tc.id
        """,
        (suite["suite_id"],),
    )
    runs = []
    for case in case_rows:
        run = await run_test_case_row(case, prompt_id=prompt_id, environment_override=environment_code)
        runs.append(run)
        db_execute(
            """
            INSERT INTO ai_test_suite_run_cases
            (suite_run_id, test_case_id, test_case_run_id, status, comparison_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (suite_run_id, case["id"], run.get("id"), run["status"], safe_json(run.get("comparison_json") or {})),
        )
    summary = suite_summary_from_runs(runs, suite)
    finished_at = now_text()
    finished = parse_timestamp(finished_at) or time.time()
    duration_ms = int(max(0, (finished - started) * 1000))
    db_execute(
        """
        INSERT INTO ai_test_suite_runs
        (suite_run_id, suite_id, endpoint, environment_code, prompt_id, prompt_version, status,
         started_at, finished_at, duration_ms, summary_json, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            suite_run_id,
            suite["suite_id"],
            endpoint,
            environment_code,
            prompt_row["id"] if prompt_row else None,
            prompt_row["version"] if prompt_row else None,
            summary["status"],
            started_at,
            finished_at,
            duration_ms,
            safe_json(summary),
            user_id,
        ),
    )
    return {
        "suite_run_id": suite_run_id,
        "suite_id": suite["suite_id"],
        "suite_name": suite["name"],
        "endpoint": endpoint,
        "environment_code": environment_code,
        "prompt_id": prompt_row["id"] if prompt_row else None,
        "prompt_version": prompt_row["version"] if prompt_row else None,
        "status": summary["status"],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "summary": summary,
        "runs": runs,
    }


def suite_row_or_404(suite_id: str) -> sqlite3.Row:
    row = db_fetchone("SELECT * FROM ai_test_suites WHERE suite_id = ?", (suite_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Test suite not found")
    return row


def status_is_passing(status: str | None) -> bool:
    return status in {"passed", "warning"}


def classify_prompt_comparison_result(baseline_status: str, candidate_status: str) -> str:
    if baseline_status == "error" or candidate_status == "error":
        return "error"
    baseline_passed = status_is_passing(baseline_status)
    candidate_passed = status_is_passing(candidate_status)
    if not baseline_passed and candidate_passed:
        return "improved"
    if baseline_passed and not candidate_passed:
        return "regressed"
    if baseline_passed and candidate_passed:
        return "unchanged_pass"
    return "unchanged_fail"


def prompt_comparison_field_differences(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    fields = ["summary", "building", "room", "priority", "work_order_type", "assign_to", "issue_to", "job_type"]
    differences = []
    for field in fields:
        baseline_value = extract_result_value(baseline, field)
        candidate_value = extract_result_value(candidate, field)
        if baseline_value != candidate_value:
            differences.append({"field": field, "baseline": baseline_value, "candidate": candidate_value})
    baseline_contract = baseline.get("contract", {}).get("valid") if isinstance(baseline.get("contract"), dict) else None
    candidate_contract = candidate.get("contract", {}).get("valid") if isinstance(candidate.get("contract"), dict) else None
    if baseline_contract != candidate_contract:
        differences.append({"field": "contract_valid", "baseline": baseline_contract, "candidate": candidate_contract})
    baseline_env = baseline.get("ai_validation", {}).get("valid") if isinstance(baseline.get("ai_validation"), dict) else None
    candidate_env = candidate.get("ai_validation", {}).get("valid") if isinstance(candidate.get("ai_validation"), dict) else None
    if baseline_env != candidate_env:
        differences.append({"field": "environment_valid", "baseline": baseline_env, "candidate": candidate_env})
    return differences


def prompt_comparison_case_json(test_case: sqlite3.Row, baseline: dict[str, Any], candidate: dict[str, Any], result: str) -> dict[str, Any]:
    return {
        "test_case_id": test_case["id"],
        "test_case_name": test_case["name"],
        "baseline": {
            "prompt_id": baseline.get("prompt_id"),
            "prompt_version": baseline.get("prompt_version"),
            "status": baseline.get("status"),
            "run_id": baseline.get("run_id"),
            "duration_ms": baseline.get("duration_ms"),
        },
        "candidate": {
            "prompt_id": candidate.get("prompt_id"),
            "prompt_version": candidate.get("prompt_version"),
            "status": candidate.get("status"),
            "run_id": candidate.get("run_id"),
            "duration_ms": candidate.get("duration_ms"),
        },
        "result": result,
        "field_differences": prompt_comparison_field_differences(baseline.get("actual_json") or {}, candidate.get("actual_json") or {}),
    }


def prompt_comparison_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total": len(cases),
        "baseline_passed": 0,
        "candidate_passed": 0,
        "improved": 0,
        "regressed": 0,
        "unchanged_pass": 0,
        "unchanged_fail": 0,
        "error": 0,
        "baseline_avg_duration_ms": 0,
        "candidate_avg_duration_ms": 0,
    }
    baseline_durations = []
    candidate_durations = []
    for case in cases:
        baseline = case.get("baseline", {})
        candidate = case.get("candidate", {})
        if status_is_passing(baseline.get("status")):
            summary["baseline_passed"] += 1
        if status_is_passing(candidate.get("status")):
            summary["candidate_passed"] += 1
        result = case.get("result")
        if result in {"improved", "regressed", "unchanged_pass", "unchanged_fail", "error"}:
            summary[result] += 1
        if isinstance(baseline.get("duration_ms"), int):
            baseline_durations.append(baseline["duration_ms"])
        if isinstance(candidate.get("duration_ms"), int):
            candidate_durations.append(candidate["duration_ms"])
    if baseline_durations:
        summary["baseline_avg_duration_ms"] = round(sum(baseline_durations) / len(baseline_durations), 1)
    if candidate_durations:
        summary["candidate_avg_duration_ms"] = round(sum(candidate_durations) / len(candidate_durations), 1)
    return summary


def active_prompt_for_endpoint(endpoint: str) -> sqlite3.Row | None:
    return db_fetchone("SELECT * FROM ai_prompt_versions WHERE endpoint = ? AND status = 'active'", (endpoint,))


def required_suite_readiness(endpoint: str, candidate_prompt_id: int, environment_code: str | None = None) -> dict[str, Any]:
    filters = ["endpoint = ?", "enabled = 1", "required_for_promotion = 1"]
    params: list[Any] = [endpoint]
    if environment_code:
        filters.append("(environment_code IS NULL OR environment_code = ?)")
        params.append(environment_code)
    rows = db_fetchall(f"SELECT * FROM ai_test_suites WHERE {' AND '.join(filters)} ORDER BY name", tuple(params))
    failures = []
    suites = []
    for suite in rows:
        run = db_fetchone(
            """
            SELECT * FROM ai_test_suite_runs
            WHERE suite_id = ? AND prompt_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (suite["suite_id"], candidate_prompt_id),
        )
        run_summary = json.loads(run["summary_json"]) if run and run["summary_json"] else None
        status = run["status"] if run else "missing"
        item = {
            "suite_id": suite["suite_id"],
            "name": suite["name"],
            "environment_code": suite["environment_code"],
            "latest_run_id": run["suite_run_id"] if run else None,
            "status": status,
            "summary": run_summary,
        }
        suites.append(item)
        if not run:
            failures.append({"suite_id": suite["suite_id"], "name": suite["name"], "reason": "No suite run found for candidate prompt."})
        elif run["status"] not in {"passed", "warning"}:
            failures.append({"suite_id": suite["suite_id"], "name": suite["name"], "reason": f"Latest suite run status is {run['status']}."})
    return {
        "required_suites_found": bool(rows),
        "required_suites_passed": not failures,
        "suite_failures": failures,
        "suites": suites,
    }


def check_prompt_promotion_gate(prompt_id: int, comparison_id: str | None = None) -> dict[str, Any]:
    candidate = prompt_version_by_id(prompt_id)
    reasons: list[str] = []
    summary: dict[str, Any] = {}
    comparison_row: sqlite3.Row | None = None
    active = None
    suite_readiness = {"required_suites_found": False, "required_suites_passed": True, "suite_failures": [], "suites": []}

    if not candidate:
        return {"allowed": False, "gate_status": "blocked", "reasons": ["Candidate prompt was not found."], "summary": summary, "comparison_id": comparison_id}
    if candidate["status"] == "archived":
        reasons.append("Archived prompts cannot be activated.")
    if candidate["status"] not in {"draft", "active"}:
        reasons.append("Candidate prompt is not eligible for activation.")

    active = active_prompt_for_endpoint(candidate["endpoint"])
    if not active:
        reasons.append(f"No current active prompt exists for endpoint {candidate['endpoint']}.")

    if not comparison_id:
        reasons.append("A completed prompt comparison is required for promotion.")
    else:
        comparison_row = db_fetchone("SELECT * FROM ai_prompt_comparisons WHERE comparison_id = ?", (comparison_id,))
        if not comparison_row:
            reasons.append("Prompt comparison was not found.")
        else:
            try:
                summary = json.loads(comparison_row["summary_json"]) if comparison_row["summary_json"] else {}
            except json.JSONDecodeError:
                summary = {}
                reasons.append("Prompt comparison summary JSON is invalid.")
            if comparison_row["endpoint"] != candidate["endpoint"]:
                reasons.append("Prompt comparison endpoint does not match the candidate prompt endpoint.")
            if active and comparison_row["baseline_prompt_id"] != active["id"]:
                reasons.append("Prompt comparison baseline is not the current active prompt.")
            if comparison_row["candidate_prompt_id"] != candidate["id"]:
                reasons.append("Prompt comparison candidate does not match this prompt.")
            if comparison_row["status"] != "completed":
                reasons.append("Prompt comparison is not completed.")
            if int(summary.get("regressed") or 0) != 0:
                reasons.append("Prompt comparison has regressions.")
            if int(summary.get("error") or 0) != 0:
                reasons.append("Prompt comparison has errors.")
            if int(summary.get("candidate_passed") or 0) < int(summary.get("baseline_passed") or 0):
                reasons.append("Candidate passed fewer test cases than the current active baseline.")
            suite_readiness = required_suite_readiness(candidate["endpoint"], candidate["id"], comparison_row["environment_code"])
            if suite_readiness["required_suites_found"] and not suite_readiness["required_suites_passed"]:
                reasons.append("One or more required test suites have not passed for the candidate prompt.")

    allowed = not reasons
    return {
        "allowed": allowed,
        "gate_status": "passed" if allowed else "blocked",
        "reasons": reasons,
        "summary": summary,
        "comparison_id": comparison_id,
        "suite_readiness": suite_readiness,
    }


def record_prompt_promotion(
    endpoint: str,
    previous_prompt_id: int | None,
    promoted_prompt_id: int,
    comparison_id: str | None,
    gate_status: str,
    override_used: bool,
    override_reason: str | None,
    promoted_by: int | None,
    summary: dict[str, Any] | None,
) -> str:
    promotion_id = "promo_" + secrets.token_hex(8)
    db_execute(
        """
        INSERT INTO ai_prompt_promotions
        (promotion_id, endpoint, previous_prompt_id, promoted_prompt_id, comparison_id, gate_status,
         override_used, override_reason, promoted_by, promoted_at, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            promotion_id,
            endpoint,
            previous_prompt_id,
            promoted_prompt_id,
            comparison_id,
            gate_status,
            1 if override_used else 0,
            override_reason,
            promoted_by,
            now_text(),
            safe_json(summary or {}),
        ),
    )
    return promotion_id


async def run_prompt_comparison(payload: PromptComparisonRequest, user: PortalUser) -> dict[str, Any]:
    baseline_prompt = prompt_version_by_id(payload.baseline_prompt_id)
    candidate_prompt = prompt_version_by_id(payload.candidate_prompt_id)
    if not baseline_prompt or not candidate_prompt:
        raise HTTPException(status_code=404, detail="Baseline or candidate prompt was not found")
    if baseline_prompt["endpoint"] != payload.endpoint or candidate_prompt["endpoint"] != payload.endpoint:
        raise HTTPException(status_code=400, detail="Both prompt versions must match the requested endpoint")
    comparison_id = "cmp_" + secrets.token_hex(8)
    started_at = now_text()
    started = parse_timestamp(started_at) or time.time()
    environment_code = payload.environment_code.upper() if payload.environment_code else None
    db_execute(
        """
        INSERT INTO ai_prompt_comparisons
        (comparison_id, endpoint, environment_code, baseline_prompt_id, candidate_prompt_id, status, started_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (comparison_id, payload.endpoint, environment_code, payload.baseline_prompt_id, payload.candidate_prompt_id, "running", started_at, user.user_id),
    )
    filters = ["endpoint = ?"]
    params: list[Any] = [payload.endpoint]
    if environment_code:
        filters.append("environment_code = ?")
        params.append(environment_code)
    if payload.enabled_only:
        filters.append("enabled = 1")
    rows = db_fetchall(f"SELECT * FROM ai_test_cases WHERE {' AND '.join(filters)} ORDER BY id", tuple(params))
    case_jsons = []
    for row in rows:
        baseline_run = await run_test_case_row(row, prompt_id=payload.baseline_prompt_id, environment_override=environment_code)
        candidate_run = await run_test_case_row(row, prompt_id=payload.candidate_prompt_id, environment_override=environment_code)
        result = classify_prompt_comparison_result(baseline_run["status"], candidate_run["status"])
        case_json = prompt_comparison_case_json(row, baseline_run, candidate_run, result)
        case_jsons.append(case_json)
        db_execute(
            """
            INSERT INTO ai_prompt_comparison_cases
            (comparison_id, test_case_id, baseline_run_id, candidate_run_id, baseline_status, candidate_status, result, comparison_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comparison_id,
                row["id"],
                baseline_run.get("run_id"),
                candidate_run.get("run_id"),
                baseline_run["status"],
                candidate_run["status"],
                result,
                safe_json(case_json),
            ),
        )
    summary = prompt_comparison_summary(case_jsons)
    finished_at = now_text()
    finished = parse_timestamp(finished_at) or time.time()
    duration_ms = int(max(0, (finished - started) * 1000))
    status = "completed"
    db_execute(
        """
        UPDATE ai_prompt_comparisons
        SET status = ?, finished_at = ?, duration_ms = ?, summary_json = ?
        WHERE comparison_id = ?
        """,
        (status, finished_at, duration_ms, safe_json(summary), comparison_id),
    )
    return {
        "comparison_id": comparison_id,
        "endpoint": payload.endpoint,
        "environment_code": environment_code,
        "baseline_prompt_id": payload.baseline_prompt_id,
        "candidate_prompt_id": payload.candidate_prompt_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "summary": summary,
        "cases": case_jsons,
    }


@app.post("/api/admin/test-cases/{test_case_id}/run")
async def run_test_case(test_case_id: int, payload: TestCaseRunRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_test_cases WHERE id = ?", (test_case_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")
    return await run_test_case_row(row, prompt_id=payload.prompt_id if payload else None, environment_override=payload.environment_code if payload else None)


@app.post("/api/admin/test-cases/run-batch")
async def run_test_case_batch(payload: TestCaseBatchRunRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    filters = []
    params: list[Any] = []
    if payload.endpoint:
        filters.append("endpoint = ?")
        params.append(payload.endpoint)
    if payload.environment_code:
        filters.append("environment_code = ?")
        params.append(payload.environment_code.upper())
    if payload.enabled_only:
        filters.append("enabled = 1")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_cases {where} ORDER BY id", tuple(params))
    runs = [await run_test_case_row(row, prompt_id=payload.prompt_id) for row in rows]
    summary = {"total": len(runs), "passed": 0, "failed": 0, "warning": 0, "error": 0, "runs": runs}
    for run in runs:
        summary[run["status"]] = summary.get(run["status"], 0) + 1
    return summary


@app.get("/api/admin/test-case-runs")
async def list_test_case_runs(status: str | None = None, limit: int = 50, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    where = "WHERE r.status = ?" if status else ""
    params: list[Any] = [status] if status else []
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT r.*, c.name AS test_case_name
        FROM ai_test_case_runs r
        LEFT JOIN ai_test_cases c ON c.id = r.test_case_id
        {where}
        ORDER BY r.id DESC LIMIT ?
        """,
        tuple(params),
    )
    return [dict(row) for row in rows]


@app.get("/api/admin/test-case-runs/{run_id}")
async def get_test_case_run(run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM ai_test_case_runs WHERE run_id = ? OR id = ?", (run_id, run_id if str(run_id).isdigit() else -1))
    if not row:
        raise HTTPException(status_code=404, detail="Test case run not found")
    item = dict(row)
    item["actual_json"] = json.loads(item["actual_json"]) if item.get("actual_json") else None
    item["comparison_json"] = json.loads(item["comparison_json"]) if item.get("comparison_json") else None
    return item


@app.get("/api/admin/test-suites")
async def list_test_suites(
    endpoint: str | None = None,
    environment_code: str | None = None,
    enabled: bool | None = None,
    required_for_promotion: bool | None = None,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("endpoint = ?")
        params.append(endpoint)
    if environment_code:
        filters.append("environment_code = ?")
        params.append(environment_code.upper())
    if enabled is not None:
        filters.append("enabled = ?")
        params.append(1 if enabled else 0)
    if required_for_promotion is not None:
        filters.append("required_for_promotion = ?")
        params.append(1 if required_for_promotion else 0)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_suites {where} ORDER BY updated_at DESC, id DESC", tuple(params))
    return [dict(row) for row in rows]


@app.post("/api/admin/test-suites")
async def create_test_suite(payload: TestSuiteRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    timestamp = now_text()
    suite_id = "suite_" + secrets.token_hex(6)
    db_execute(
        """
        INSERT INTO ai_test_suites
        (suite_id, name, endpoint, environment_code, description, enabled, required_for_promotion,
         min_pass_rate, zero_regression_required, zero_error_required, tags, created_at, updated_at, created_by, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            suite_id,
            payload.name,
            payload.endpoint,
            payload.environment_code.upper() if payload.environment_code else None,
            payload.description,
            1 if payload.enabled else 0,
            1 if payload.required_for_promotion else 0,
            payload.min_pass_rate,
            1 if payload.zero_regression_required else 0,
            1 if payload.zero_error_required else 0,
            payload.tags,
            timestamp,
            timestamp,
            user.user_id,
            user.user_id,
        ),
    )
    return {"status": "ok", "suite_id": suite_id}


@app.post("/api/admin/test-suites/run-batch")
async def run_test_suite_batch(payload: TestSuiteBatchRunRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    filters = []
    params: list[Any] = []
    if payload.endpoint:
        filters.append("endpoint = ?")
        params.append(payload.endpoint)
    if payload.environment_code:
        filters.append("environment_code = ?")
        params.append(payload.environment_code.upper())
    if payload.required_only:
        filters.append("required_for_promotion = 1")
    if payload.enabled_only:
        filters.append("enabled = 1")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db_fetchall(f"SELECT * FROM ai_test_suites {where} ORDER BY id", tuple(params))
    runs = [await run_test_suite_row(row, prompt_id=payload.prompt_id, environment_override=payload.environment_code, user_id=user.user_id) for row in rows]
    summary: dict[str, Any] = {"total_suites": len(runs), "passed": 0, "failed": 0, "warning": 0, "error": 0, "runs": runs}
    for run in runs:
        status = run["status"]
        summary[status] = summary.get(status, 0) + 1
    return summary


@app.get("/api/admin/test-suite-runs")
async def list_test_suite_runs(status: str | None = None, limit: int = 50, user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    where = "WHERE r.status = ?" if status else ""
    params: list[Any] = [status] if status else []
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT r.*, s.name AS suite_name
        FROM ai_test_suite_runs r
        LEFT JOIN ai_test_suites s ON s.suite_id = r.suite_id
        {where}
        ORDER BY r.id DESC LIMIT ?
        """,
        tuple(params),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
        result.append(item)
    return result


@app.get("/api/admin/test-suite-runs/{suite_run_id}")
async def get_test_suite_run(suite_run_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone(
        """
        SELECT r.*, s.name AS suite_name
        FROM ai_test_suite_runs r
        LEFT JOIN ai_test_suites s ON s.suite_id = r.suite_id
        WHERE r.suite_run_id = ?
        """,
        (suite_run_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Test suite run not found")
    cases = db_fetchall(
        """
        SELECT rc.*, tc.name AS test_case_name, tcr.run_id AS workflow_run_id
        FROM ai_test_suite_run_cases rc
        LEFT JOIN ai_test_cases tc ON tc.id = rc.test_case_id
        LEFT JOIN ai_test_case_runs tcr ON tcr.id = rc.test_case_run_id
        WHERE rc.suite_run_id = ?
        ORDER BY rc.id
        """,
        (suite_run_id,),
    )
    item = dict(row)
    item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
    item["cases"] = []
    for case in cases:
        case_item = dict(case)
        case_item["comparison_json"] = json.loads(case_item["comparison_json"]) if case_item.get("comparison_json") else None
        item["cases"].append(case_item)
    return item


@app.get("/api/admin/test-suites/{suite_id}")
async def get_test_suite(suite_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = suite_row_or_404(suite_id)
    cases = db_fetchall(
        """
        SELECT sc.*, tc.name, tc.endpoint, tc.environment_code, tc.input_text, tc.enabled AS test_case_enabled
        FROM ai_test_suite_cases sc
        JOIN ai_test_cases tc ON tc.id = sc.test_case_id
        WHERE sc.suite_id = ?
        ORDER BY sc.sort_order, tc.id
        """,
        (suite_id,),
    )
    item = dict(row)
    item["cases"] = [dict(case) for case in cases]
    return item


@app.patch("/api/admin/test-suites/{suite_id}")
async def patch_test_suite(suite_id: str, payload: TestSuitePatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = suite_row_or_404(suite_id)
    environment_code = payload.environment_code.upper() if payload.environment_code is not None and payload.environment_code else (None if payload.environment_code == "" else row["environment_code"])
    db_execute(
        """
        UPDATE ai_test_suites
        SET name = ?, endpoint = ?, environment_code = ?, description = ?, enabled = ?, required_for_promotion = ?,
            min_pass_rate = ?, zero_regression_required = ?, zero_error_required = ?, tags = ?, updated_at = ?, updated_by = ?
        WHERE suite_id = ?
        """,
        (
            payload.name if payload.name is not None else row["name"],
            payload.endpoint if payload.endpoint is not None else row["endpoint"],
            environment_code,
            payload.description if payload.description is not None else row["description"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            1 if (payload.required_for_promotion if payload.required_for_promotion is not None else bool(row["required_for_promotion"])) else 0,
            payload.min_pass_rate if payload.min_pass_rate is not None else row["min_pass_rate"],
            1 if (payload.zero_regression_required if payload.zero_regression_required is not None else bool(row["zero_regression_required"])) else 0,
            1 if (payload.zero_error_required if payload.zero_error_required is not None else bool(row["zero_error_required"])) else 0,
            payload.tags if payload.tags is not None else row["tags"],
            now_text(),
            user.user_id,
            suite_id,
        ),
    )
    return {"status": "ok", "suite_id": suite_id}


@app.delete("/api/admin/test-suites/{suite_id}")
async def delete_test_suite(suite_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    suite_row_or_404(suite_id)
    db_execute("DELETE FROM ai_test_suite_cases WHERE suite_id = ?", (suite_id,))
    db_execute("DELETE FROM ai_test_suites WHERE suite_id = ?", (suite_id,))
    return {"status": "ok", "suite_id": suite_id}


@app.post("/api/admin/test-suites/{suite_id}/cases")
async def add_test_suite_case(suite_id: str, payload: TestSuiteCaseRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    suite_row_or_404(suite_id)
    case = db_fetchone("SELECT id FROM ai_test_cases WHERE id = ?", (payload.test_case_id,))
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    try:
        db_execute(
            """
            INSERT INTO ai_test_suite_cases (suite_id, test_case_id, sort_order, enabled)
            VALUES (?, ?, ?, ?)
            """,
            (suite_id, payload.test_case_id, payload.sort_order, 1 if payload.enabled else 0),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Test case is already in this suite") from exc
    return {"status": "ok", "suite_id": suite_id, "test_case_id": payload.test_case_id}


@app.delete("/api/admin/test-suites/{suite_id}/cases/{test_case_id}")
async def remove_test_suite_case(suite_id: str, test_case_id: int, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    suite_row_or_404(suite_id)
    db_execute("DELETE FROM ai_test_suite_cases WHERE suite_id = ? AND test_case_id = ?", (suite_id, test_case_id))
    return {"status": "ok", "suite_id": suite_id, "test_case_id": test_case_id}


@app.post("/api/admin/test-suites/{suite_id}/run")
async def run_test_suite(suite_id: str, payload: TestSuiteRunRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    suite = suite_row_or_404(suite_id)
    return await run_test_suite_row(suite, prompt_id=payload.prompt_id if payload else None, environment_override=payload.environment_code if payload else None, user_id=user.user_id)


@app.get("/api/admin/regression-dashboard")
async def regression_dashboard(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return build_regression_dashboard()


@app.post("/api/admin/prompt-comparisons")
async def create_prompt_comparison(payload: PromptComparisonRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    return await run_prompt_comparison(payload, user)


@app.get("/api/admin/prompt-comparisons")
async def list_prompt_comparisons(
    endpoint: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("c.endpoint = ?")
        params.append(endpoint)
    if status:
        filters.append("c.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT c.*, bp.version AS baseline_version, cp.version AS candidate_version
        FROM ai_prompt_comparisons c
        LEFT JOIN ai_prompt_versions bp ON bp.id = c.baseline_prompt_id
        LEFT JOIN ai_prompt_versions cp ON cp.id = c.candidate_prompt_id
        {where}
        ORDER BY c.id DESC LIMIT ?
        """,
        tuple(params),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
        result.append(item)
    return result


@app.get("/api/admin/prompt-comparisons/{comparison_id}")
async def get_prompt_comparison(comparison_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone(
        """
        SELECT c.*, bp.version AS baseline_version, cp.version AS candidate_version
        FROM ai_prompt_comparisons c
        LEFT JOIN ai_prompt_versions bp ON bp.id = c.baseline_prompt_id
        LEFT JOIN ai_prompt_versions cp ON cp.id = c.candidate_prompt_id
        WHERE c.comparison_id = ?
        """,
        (comparison_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Prompt comparison not found")
    cases = db_fetchall(
        """
        SELECT pc.*, tc.name AS test_case_name
        FROM ai_prompt_comparison_cases pc
        LEFT JOIN ai_test_cases tc ON tc.id = pc.test_case_id
        WHERE pc.comparison_id = ?
        ORDER BY pc.id
        """,
        (comparison_id,),
    )
    item = dict(row)
    item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
    item["cases"] = []
    for case in cases:
        case_item = dict(case)
        case_item["comparison_json"] = json.loads(case_item["comparison_json"]) if case_item.get("comparison_json") else None
        item["cases"].append(case_item)
    return item


@app.get("/api/admin/prompt-promotions")
async def list_prompt_promotions(
    endpoint: str | None = None,
    limit: int = 50,
    user: PortalUser = Depends(current_admin),
) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    if endpoint:
        filters.append("p.endpoint = ?")
        params.append(endpoint)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(max(1, min(int(limit or 50), 200)))
    rows = db_fetchall(
        f"""
        SELECT p.*, prev.version AS previous_version, promoted.version AS promoted_version, u.username AS promoted_by_username
        FROM ai_prompt_promotions p
        LEFT JOIN ai_prompt_versions prev ON prev.id = p.previous_prompt_id
        LEFT JOIN ai_prompt_versions promoted ON promoted.id = p.promoted_prompt_id
        LEFT JOIN users u ON u.user_id = p.promoted_by
        {where}
        ORDER BY p.id DESC LIMIT ?
        """,
        tuple(params),
    )
    result = []
    for row in rows:
        item = dict(row)
        item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
        result.append(item)
    return result


@app.get("/api/admin/prompt-promotions/{promotion_id}")
async def get_prompt_promotion(promotion_id: str, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone(
        """
        SELECT p.*, prev.version AS previous_version, promoted.version AS promoted_version, u.username AS promoted_by_username
        FROM ai_prompt_promotions p
        LEFT JOIN ai_prompt_versions prev ON prev.id = p.previous_prompt_id
        LEFT JOIN ai_prompt_versions promoted ON promoted.id = p.promoted_prompt_id
        LEFT JOIN users u ON u.user_id = p.promoted_by
        WHERE p.promotion_id = ?
        """,
        (promotion_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Prompt promotion not found")
    item = dict(row)
    item["summary_json"] = json.loads(item["summary_json"]) if item.get("summary_json") else None
    return item


@app.get("/api/admin/api-keys")
async def list_api_keys(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT key_id, name, enabled, owner, created_at, last_used_at, usage_count FROM api_keys ORDER BY created_at DESC")
    return [dict(row) for row in rows]


@app.post("/api/admin/api-keys")
async def create_api_key(payload: ApiKeyCreateRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    api_key = "cmms_" + secrets.token_urlsafe(32)
    key_id = "key_" + secrets.token_hex(4)
    db_execute(
        """
        INSERT INTO api_keys (key_id, name, key_hash, enabled, owner, created_at)
        VALUES (?, ?, ?, 1, ?, ?)
        """,
        (key_id, payload.name.strip(), hash_text(api_key), payload.owner, now_text()),
    )
    logger.info("api_key_created key_id=%s name=%s user=%s", key_id, payload.name.strip(), user.username)
    return {"key_id": key_id, "name": payload.name.strip(), "api_key": api_key, "enabled": True}


@app.patch("/api/admin/api-keys/{key_id}")
async def patch_api_key(key_id: str, payload: ApiKeyPatchRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone("SELECT * FROM api_keys WHERE key_id = ?", (key_id,))
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    db_execute(
        "UPDATE api_keys SET name = ?, enabled = ? WHERE key_id = ?",
        (
            payload.name if payload.name is not None else row["name"],
            1 if (payload.enabled if payload.enabled is not None else bool(row["enabled"])) else 0,
            key_id,
        ),
    )
    return {"status": "ok", "key_id": key_id}


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
    row = db_fetchone(
        """
        SELECT c.*, r.actual_json
        FROM ai_test_case_runs r
        JOIN ai_test_cases c ON c.id = r.test_case_id
        WHERE r.run_id = ?
        ORDER BY r.id DESC LIMIT 1
        """,
        (run_id,),
    )
    if not row:
        raise HTTPException(status_code=400, detail="This workflow run cannot create a test case because the original input text was not stored.")
    expected_json = payload.expected_json
    if expected_json is None and row["actual_json"]:
        try:
            actual = json.loads(row["actual_json"])
            expected_json = {
                "building": extract_result_value(actual, "building"),
                "room": extract_result_value(actual, "room"),
                "priority": extract_result_value(actual, "priority"),
                "work_order_type": extract_result_value(actual, "work_order_type"),
                "contract_valid": actual.get("contract", {}).get("valid") if isinstance(actual.get("contract"), dict) else None,
                "environment_valid": actual.get("ai_validation", {}).get("valid") if isinstance(actual.get("ai_validation"), dict) else None,
            }
        except json.JSONDecodeError:
            expected_json = None
    request_payload = TestCaseRequest(
        name=payload.name,
        endpoint=row["endpoint"],
        environment_code=row["environment_code"],
        input_text=row["input_text"],
        source="workflow_run",
        expected_json=expected_json,
        enabled=True,
        tags=payload.tags,
        notes=payload.notes,
    )
    return await create_test_case(request_payload, user)


@app.post("/api/admin/workflow-runs/{run_id}/replay")
async def replay_workflow_run(run_id: str, payload: TestCaseRunRequest | None = None, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    row = db_fetchone(
        """
        SELECT c.*
        FROM ai_test_case_runs r
        JOIN ai_test_cases c ON c.id = r.test_case_id
        WHERE r.run_id = ?
        ORDER BY r.id DESC LIMIT 1
        """,
        (run_id,),
    )
    if not row:
        raise HTTPException(status_code=400, detail="This workflow run cannot be replayed because the original input text was not stored.")
    return await run_test_case_row(row, prompt_id=payload.prompt_id if payload else None, environment_override=payload.environment_code if payload else None)


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


@app.get("/api/kb/status")
async def kb_status(user: PortalUser = Depends(current_user)) -> dict[str, Any]:
    return {
        "status": "placeholder",
        "message": "Knowledge base sources, indexing, and retrieval testing will be added in a future version.",
        "planned_interfaces": ["sources", "indexes", "retrieval_test"],
    }


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
    messages, prompt_meta = prompt_messages("summarize-work-order", {"text": payload.text})
    summary = await call_ollama(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
    return SummaryResponse(summary=summary)


@app.post("/api/ai/cmms-assistant", response_model=AssistantResponse, dependencies=[Depends(require_api_key)])
async def cmms_assistant(request: Request, payload: TextRequest) -> AssistantResponse:
    if payload.environment_code:
        request.state.environment_code = payload.environment_code
    messages, prompt_meta = prompt_messages("cmms-assistant", {"text": payload.text})
    content = await call_ollama(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
    return AssistantResponse(
        mode="cmms-assistant",
        response=content,
        model=MODEL_NAME,
        safety={
            "advisory_only": True,
            "cmms_write_back": False,
            "work_order_created": False,
            "email_sent": False,
        },
    )


@app.post("/api/ai/extract-work-order-fields", response_model=ExtractFieldsResponse, dependencies=[Depends(require_api_key)])
async def extract_work_order_fields(request: Request, payload: ExtractFieldsRequest) -> ExtractFieldsResponse:
    valid_buildings, valid_priorities, env_code = resolve_validation_lists(payload)
    if env_code:
        request.state.environment_code = env_code
    messages, prompt_meta = prompt_messages(
        "extract-work-order-fields",
        {
            "text": payload.text,
            "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
            "valid_buildings": valid_buildings,
            "valid_priorities": valid_priorities,
        },
    )
    content = await call_ollama(messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"])
    data = parse_json_response(content)
    return validate_extracted_fields(data, valid_buildings, valid_priorities)


@app.post("/api/ai/cmms-intake", response_model=IntakeResponse, dependencies=[Depends(require_api_key)])
async def cmms_intake(request: Request, payload: ExtractFieldsRequest) -> IntakeResponse:
    env_hint = payload.environment_code.upper() if payload.environment_code else None
    run_id = start_workflow_run(
        "cmms-intake",
        environment_code=env_hint,
        user_id=getattr(request.state, "user_id", None),
        api_key_id=getattr(request.state, "api_key_id", None),
        source=payload.source,
    )
    current_step: int | None = None
    try:
        current_step = start_workflow_step(
            run_id,
            "request_received",
            10,
            input_summary=f"{redacted_summary(payload.text)} | source={payload.source or 'text'} environment={env_hint or 'none'}",
        )
        finish_workflow_step(current_step, "passed", output_summary="Request accepted for controlled intake workflow")
        current_step = None

        valid_buildings, valid_priorities, env_code = resolve_validation_lists(payload)
        if env_code:
            request.state.environment_code = env_code

        current_step = start_workflow_step(
            run_id,
            "model_extraction",
            20,
            model=MODEL_NAME,
            prompt_version="pending",
            input_summary=f"text_length={len(payload.text)} buildings={len(valid_buildings)} priorities={len(valid_priorities)}",
        )
        intake_messages, prompt_meta = intake_prompt_messages(
            {
                "text": payload.text,
                "allowed_request_types": sorted(ALLOWED_REQUEST_TYPES),
                "valid_buildings": valid_buildings,
                "valid_priorities": valid_priorities,
            }
        )
        db_execute(
            "UPDATE workflow_run_steps SET model = ?, prompt_version = ? WHERE id = ?",
            (prompt_meta["model"], f"{prompt_meta['prompt_id']}:{prompt_meta['prompt_version']}", current_step),
        )
        classifier_data = parse_json_response(await call_ollama(intake_messages["classifier"], temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
        extractor_data = parse_json_response(await call_ollama(intake_messages["field_extractor"], temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
        request_type, confidence, fields, validation = validate_intake(
            classifier_data.get("request_type"),
            classifier_data.get("confidence"),
            extractor_data,
            valid_buildings,
            valid_priorities,
        )
        draft_context = {
            "text": payload.text,
            "request_type": request_type,
            "fields": fields.model_dump(),
            "validation": validation.model_dump(),
        }
        draft_messages = [
            intake_messages["draft_generator"][0],
            {"role": "user", "content": json.dumps(draft_context)},
        ]
        draft_data = parse_json_response(await call_ollama(draft_messages, temperature=prompt_meta["temperature"], model=prompt_meta["model"]))
        finish_workflow_step(
            current_step,
            "passed",
            output_summary=f"type={request_type} confidence={confidence:.2f} missing={len(validation.missing_fields)}",
            output_json={
                "request_type": request_type,
                "confidence": confidence,
                "model_call_count": 3,
                "prompt_id": prompt_meta["prompt_id"],
                "prompt_version": prompt_meta["prompt_version"],
                "temperature": prompt_meta["temperature"],
                "fields": fields.model_dump(),
                "missing_fields": validation.missing_fields,
            },
        )
        current_step = None

        result_payload = {
            "summary": fields.summary,
            "building": fields.building,
            "room": fields.room,
            "priority": fields.priority,
            "work_order_type": request_type,
            "assign_to": None,
            "issue_to": None,
            "job_type": None,
            "confidence": confidence,
        }

        current_step = start_workflow_step(run_id, "output_contract_validation", 30, input_summary="endpoint=cmms-intake")
        contract_validation = validate_output_contract("cmms-intake", result_payload)
        contract_status = "passed" if contract_validation["valid"] else "failed"
        finish_workflow_step(
            current_step,
            contract_status,
            output_summary=f"contract_valid={contract_validation['valid']} errors={len(contract_validation['errors'])}",
            output_json={
                "contract_version": contract_validation["contract_version"],
                "valid": contract_validation["valid"],
                "error_count": len(contract_validation["errors"]),
                "warning_count": len(contract_validation["warnings"]),
            },
        )
        current_step = None
        contract_block = {
            "version": contract_validation["contract_version"],
            "valid": contract_validation["valid"],
            "errors": contract_validation["errors"],
            "warnings": contract_validation["warnings"],
        }

        current_step = start_workflow_step(run_id, "environment_validation", 40, input_summary=f"environment={env_code or 'none'}")
        if env_code and contract_validation["valid"]:
            ai_validation = validate_ai_output(
                env_code,
                contract_validation["normalized_payload"],
            )
            ai_validation["enabled"] = True
            ai_validation["status"] = "completed"
            env_status = "failed" if ai_validation["valid"] is False else ("warning" if ai_validation.get("warnings") else "passed")
            finish_workflow_step(
                current_step,
                env_status,
                output_summary=f"validation_valid={ai_validation['valid']} warnings={len(ai_validation.get('warnings', []))} errors={len(ai_validation.get('errors', []))}",
                output_json={
                    "valid": ai_validation["valid"],
                    "error_count": len(ai_validation.get("errors", [])),
                    "warning_count": len(ai_validation.get("warnings", [])),
                    "normalized": ai_validation.get("normalized", {}),
                },
            )
            current_step = None
        else:
            ai_validation = skipped_ai_validation() if env_code else {
                "enabled": False,
                "valid": None,
                "status": "not_run",
                "message": "No environment_code was supplied.",
                "errors": [],
                "warnings": [],
                "normalized": {},
            }
            finish_workflow_step(
                current_step,
                "skipped",
                output_summary="Skipped because output contract validation failed." if env_code else "Skipped because no environment_code was supplied.",
                output_json={"status": ai_validation.get("status"), "valid": ai_validation.get("valid")},
            )
            current_step = None

        current_step = start_workflow_step(run_id, "response_composed", 50)
        drafts = IntakeDrafts(
            draft_wo_description=str(draft_data.get("draft_wo_description") or fields.summary),
            internal_note=str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."),
            client_reply=str(draft_data.get("client_reply") or "Thanks, we captured your request."),
        )
        run_status = "failed" if not contract_validation["valid"] else ("completed_with_warnings" if ai_validation.get("warnings") else "completed")
        finish_workflow_step(current_step, "passed", output_summary=f"run_status={run_status}")
        current_step = None
        finish_workflow_run(run_id, run_status)
        return IntakeResponse(
            run_id=run_id,
            endpoint="cmms-intake",
            environment_code=env_code,
            trace={"available": True, "run_id": run_id},
            contract=contract_block,
            result=contract_validation["normalized_payload"] if contract_validation["valid"] else result_payload,
            ai_validation=ai_validation,
            raw={"included": False},
            request_type=request_type,
            classification_confidence=confidence,
            fields=fields,
            validation=validation,
            drafts=drafts,
            model=MODEL_NAME,
        )
    except Exception as exc:
        if current_step is not None:
            fail_workflow_step(current_step, str(exc))
        finish_workflow_run(run_id, "failed", str(exc))
        raise
