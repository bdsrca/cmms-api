from __future__ import annotations

import asyncio
import inspect
import logging
import os
import secrets
import subprocess
import threading
import time
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response

from .ai_endpoints import (
    call_ollama as ai_call_ollama,
    execute_ai_endpoint_for_test as execute_ai_endpoint_for_test_helper,
)
from .ai_routes import build_ai_router
from .api_keys import migrate_json_api_keys
from .auth_routes import router as auth_router
from .chat_console_routes import router as chat_console_router
from .cmms_connector_routes import router as cmms_connector_router
from .cmms_connectors import migrate_plaintext_connector_secrets
from .core_routes import router as core_router
from .config import (
    ALLOWED_REQUEST_TYPES,
    CODE_CATEGORIES,
    DEFAULT_CMMS_INTAKE_CONTRACT,
    DEFAULT_PROMPT_VERSIONS,
    DEFAULT_VALIDATION_RULES,
    MODEL_NAME,
    OLLAMA_CHAT_URL,
    SERVICE_NAME,
    build_ai_config_status,
)
from .db import (
    BASE_DIR,
    DATA_DIR,
    LOG_DIR,
    LOG_FILE,
    db_execute,
    init_db as init_database,
)
from .environments import (
    get_environment_values,
    seed_default_environment,
)
from .environment_routes import router as environment_router
from .security import (
    AuthContext,
    PortalUser,
    bootstrap_admin_user,
    hash_password,
)
from .output_contracts import (
    active_contract,
    seed_default_output_contracts,
)
from .operations_routes import router as operations_router
from .management_routes import build_management_router
from .models import (
    AssistantResponse,
    EmailIntakeRequest,
    ExtractFieldsRequest,
    ExtractFieldsResponse,
    IntakeResponse,
    SummaryResponse,
    TextRequest,
)
from .prompts import seed_default_prompt_versions
from .prompt_routes import build_prompt_router
from .test_runner_callbacks import build_test_runner_callbacks
from .test_routes import build_test_router
from .validation_rules import (
    validate_ai_output,
)
from .validation_contract_routes import router as validation_contract_router
from .workflow_trace import (
    cleanup_workflow_runs,
)


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
app.include_router(chat_console_router)
app.include_router(environment_router)
app.include_router(validation_contract_router)
app.include_router(operations_router)
app.include_router(cmms_connector_router)


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_ms() -> int:
    return int(time.time() * 1000)


def require_local_control(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="System controls are local-only")
    expected_key = os.getenv("LOCAL_CONTROL_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="LOCAL_CONTROL_API_KEY environment variable is not set")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def call_ollama(
    messages: list[dict[str, str]],
    timeout: int = 120,
    temperature: float | None = None,
    model: str = MODEL_NAME,
    response_format: str | None = None,
) -> str:
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "temperature": temperature,
        "model": model,
    }
    if response_format is not None and supports_kwarg(ai_call_ollama, "response_format"):
        kwargs["response_format"] = response_format
    return await ai_call_ollama(messages, **kwargs)


def supports_kwarg(func: Any, name: str) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return True
    return any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()) or name in signature.parameters


async def is_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True


async def configured_ollama_models() -> list[str] | None:
    tags_url = OLLAMA_CHAT_URL.replace("/api/chat", "/api/tags")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(tags_url)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return None
    return [item["name"] for item in models if isinstance(item, dict) and isinstance(item.get("name"), str)]


async def log_ai_config_warnings() -> None:
    available_models = await configured_ollama_models()
    if available_models is None:
        logger.warning("ai_config_model_check_skipped reason=ollama_tags_unavailable")
        return
    for warning in build_ai_config_status(available_models=available_models)["warnings"]:
        logger.warning("ai_config_warning message=%s", warning)


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


def shutdown_process_later() -> None:
    def delayed_exit() -> None:
        time.sleep(0.5)
        logger.info("service_forced_shutdown requested_by=ui")
        os._exit(0)

    threading.Thread(target=delayed_exit, daemon=True).start()


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


async def execute_ai_endpoint_for_test(
    endpoint: str,
    input_text: str,
    environment_code: str | None,
    source: str = "test_case",
    prompt_id: int | None = None,
    reviewer_prompt_id: int | None = None,
) -> dict[str, Any]:
    return await execute_ai_endpoint_for_test_helper(
        endpoint,
        input_text,
        environment_code,
        source=source,
        prompt_id=prompt_id,
        reviewer_prompt_id=reviewer_prompt_id,
        request_factory=ExtractFieldsRequest,
        call_ollama_func=call_ollama,
    )


@app.on_event("startup")
async def startup() -> None:
    init_database(
        seed_callbacks=[
            migrate_json_api_keys,
            migrate_plaintext_connector_secrets,
            bootstrap_admin_user,
            seed_default_environment,
            seed_default_output_contracts,
            seed_default_prompt_versions,
        ]
    )
    await log_ai_config_warnings()
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


test_case_runner_kwargs, test_suite_runner_kwargs, run_test_case_row_for_prompt_comparison = build_test_runner_callbacks(
    execute_ai_endpoint_for_test
)


async def route_call_ollama(*args: Any, **kwargs: Any) -> str:
    return await call_ollama(*args, **kwargs)


app.include_router(
    build_prompt_router(
        call_ollama=route_call_ollama,
        get_environment_values=get_environment_values,
        run_test_case_row_for_prompt_comparison=run_test_case_row_for_prompt_comparison,
    )
)


app.include_router(
    build_test_router(
        test_case_runner_kwargs=test_case_runner_kwargs,
        test_suite_runner_kwargs=test_suite_runner_kwargs,
    )
)


app.include_router(
    build_management_router(
        require_local_control=require_local_control,
        is_ollama_running=is_ollama_running,
        wait_for_ollama=wait_for_ollama,
        start_ollama_process=start_ollama_process,
        stop_ollama_process=stop_ollama_process,
        shutdown_process_later=shutdown_process_later,
    )
)


app.include_router(
    build_ai_router(
        call_ollama=route_call_ollama,
        text_request_model=TextRequest,
        summary_response_model=SummaryResponse,
        assistant_response_model=AssistantResponse,
        extract_fields_request_model=ExtractFieldsRequest,
        extract_fields_response_model=ExtractFieldsResponse,
        email_intake_request_model=EmailIntakeRequest,
        intake_response_model=IntakeResponse,
    )
)
