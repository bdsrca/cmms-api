"""API key, settings, and local system/process route registration."""

from collections.abc import Awaitable, Callable
import inspect
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .api_keys import (
    create_api_key as create_api_key_helper,
    list_api_keys as list_api_keys_helper,
    patch_api_key as patch_api_key_helper,
)
from .config import MODEL_NAME, OLLAMA_CHAT_URL, SERVICE_NAME, build_ai_config_status
from .db import LOG_FILE, db_execute, db_fetchone
from .operations_routes import LogResponse, read_log_lines
from .security import PortalUser, current_admin, current_user
from .system_setup import (
    build_setup_status,
    create_system_backup,
    list_system_backups,
    preview_system_restore,
)


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    owner: str | None = None
    allowed_endpoints: list[str] | None = None
    allowed_environments: list[str] | None = None


class ApiKeyPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    allowed_endpoints: list[str] | None = None
    allowed_environments: list[str] | None = None


class SettingPatchRequest(BaseModel):
    value: str


class SystemStatusResponse(BaseModel):
    service: str
    model: str
    api_running: bool
    ollama_running: bool
    log_file: str


class RestorePreviewRequest(BaseModel):
    backup_id: str | None = None
    file_name: str | None = None


def now_text() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def ollama_model_names() -> list[str] | None:
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
    names: list[str] = []
    for item in models:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def build_management_router(
    *,
    require_local_control: Callable[[Request], None],
    is_ollama_running: Callable[[], Awaitable[bool]],
    wait_for_ollama: Callable[[], Awaitable[bool]],
    start_ollama_process: Callable[[], None],
    stop_ollama_process: Callable[[], None],
    shutdown_process_later: Callable[[], None],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/api-keys")
    async def list_api_keys(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
        return list_api_keys_helper()

    @router.post("/api/admin/api-keys")
    async def create_api_key(payload: ApiKeyCreateRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return create_api_key_helper(payload, user)

    @router.patch("/api/admin/api-keys/{key_id}")
    async def patch_api_key(
        key_id: str,
        payload: ApiKeyPatchRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, Any]:
        return patch_api_key_helper(key_id, payload)

    @router.get("/api/admin/settings/{key}")
    async def get_setting(key: str, user: PortalUser = Depends(current_admin)) -> dict[str, str]:
        row = db_fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return {"key": key, "value": row["value"] if row else ""}

    @router.patch("/api/admin/settings/{key}")
    async def patch_setting(
        key: str,
        payload: SettingPatchRequest,
        user: PortalUser = Depends(current_admin),
    ) -> dict[str, str]:
        db_execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, payload.value, now_text()),
        )
        return {"status": "ok", "key": key}

    @router.get("/api/admin/setup/status")
    async def setup_status(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        return build_setup_status()

    @router.get("/api/admin/ai-config")
    async def ai_config(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        available_models = await ollama_model_names()
        status = build_ai_config_status(available_models=available_models)
        if available_models is None:
            status["warnings"].append("Could not verify configured models because Ollama tags were unavailable.")
        return status

    @router.post("/api/admin/system/backup")
    async def create_backup(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        try:
            return create_system_backup(created_by=user.username)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get("/api/admin/system/backups")
    async def list_backups(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
        return list_system_backups()

    @router.post("/api/admin/system/restore-preview")
    async def restore_preview(payload: RestorePreviewRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        try:
            return preview_system_restore(backup_id=payload.backup_id, file_name=payload.file_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/api/system/status",
        response_model=SystemStatusResponse,
        dependencies=[Depends(require_local_control)],
    )
    async def system_status(user: PortalUser = Depends(current_admin)) -> SystemStatusResponse:
        return SystemStatusResponse(
            service=SERVICE_NAME,
            model=MODEL_NAME,
            api_running=True,
            ollama_running=await maybe_await(is_ollama_running()),
            log_file=str(LOG_FILE),
        )

    @router.get(
        "/api/system/logs",
        response_model=LogResponse,
        dependencies=[Depends(require_local_control)],
    )
    async def system_logs(lines: int = 200, user: PortalUser = Depends(current_user)) -> LogResponse:
        return LogResponse(log_file=str(LOG_FILE), lines=read_log_lines(lines))

    @router.post("/api/system/ollama/start", dependencies=[Depends(require_local_control)])
    async def start_ollama(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        if await maybe_await(is_ollama_running()):
            return {"status": "ok", "ollama_running": True, "message": "Ollama is already running"}
        start_ollama_process()
        ollama_running = await maybe_await(wait_for_ollama())
        if not ollama_running:
            raise HTTPException(status_code=500, detail="Ollama did not become ready after startup")
        return {"status": "ok", "ollama_running": True, "message": "Ollama started"}

    @router.post("/api/system/ollama/stop", dependencies=[Depends(require_local_control)])
    async def stop_ollama(user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
        stop_ollama_process()
        return {"status": "ok", "ollama_running": await maybe_await(is_ollama_running())}

    @router.post("/api/system/shutdown", dependencies=[Depends(require_local_control)])
    async def shutdown_api(background_tasks: BackgroundTasks, user: PortalUser = Depends(current_admin)) -> dict[str, str]:
        background_tasks.add_task(shutdown_process_later)
        return {"status": "stopping", "message": "FastAPI service is stopping"}

    return router
