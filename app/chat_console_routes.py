"""Admin-only generic Ollama chat console routes."""

from __future__ import annotations

import json
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import OLLAMA_CHAT_URL
from .security import PortalUser, current_admin


OLLAMA_TAGS_URL = OLLAMA_CHAT_URL.replace("/api/chat", "/api/tags")


class ChatConsoleMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatConsoleRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    thinking_enabled: bool = False
    response_num_predict: int = Field(default=1024, ge=128, le=4096)
    images: list[str] = Field(default_factory=list, max_length=4)
    messages: list[ChatConsoleMessage] = Field(min_length=1, max_length=40)


async def _ollama_models() -> list[dict[str, str]]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(OLLAMA_TAGS_URL)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to Ollama") from exc

    data = response.json()
    models = data.get("models", [])
    if not isinstance(models, list):
        return []
    return [
        {"id": str(item.get("name") or item.get("model")), "provider": "ollama"}
        for item in models
        if isinstance(item, dict) and (item.get("name") or item.get("model"))
    ]


def _messages_for_ollama(payload: ChatConsoleRequest) -> list[dict[str, object]]:
    messages = [message.model_dump() for message in payload.messages]
    directive = "/think" if payload.thinking_enabled else "/no_think"
    for index in range(len(messages) - 1, -1, -1):
        if messages[index]["role"] == "user":
            messages[index]["content"] = f"{directive}\n\n{messages[index]['content']}"
            if payload.images:
                messages[index]["images"] = payload.images
            break
    return messages


def _ollama_chat_payload(payload: ChatConsoleRequest, stream: bool) -> dict[str, object]:
    return {
        "model": payload.model,
        "stream": stream,
        "think": payload.thinking_enabled,
        "options": {"num_predict": payload.response_num_predict},
        "messages": _messages_for_ollama(payload),
    }


def _chat_content_from_message(message: dict[str, object]) -> str:
    content = str(message.get("content") or "")
    thinking = str(message.get("thinking") or "")
    return content or thinking


router = APIRouter(prefix="/api/admin/chat-test", dependencies=[Depends(current_admin)])


@router.get("/models")
async def chat_console_models(user: PortalUser = Depends(current_admin)) -> dict[str, object]:
    del user
    models = await _ollama_models()
    return {"provider": "ollama", "model": models[0]["id"] if models else "", "models": models}


@router.post("/message")
async def chat_console_message(payload: ChatConsoleRequest, user: PortalUser = Depends(current_admin)) -> dict[str, str]:
    del user
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                OLLAMA_CHAT_URL,
                json=_ollama_chat_payload(payload, stream=False),
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail="Ollama request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to Ollama") from exc

    data = response.json()
    message = data.get("message") or {}
    content = (_chat_content_from_message(message) or data.get("response") or "").strip()
    if not content:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response")

    return {"message": content, "provider": "ollama", "model": payload.model}


@router.post("/message/stream")
async def chat_console_message_stream(payload: ChatConsoleRequest, user: PortalUser = Depends(current_admin)) -> StreamingResponse:
    del user

    async def stream_ollama():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    OLLAMA_CHAT_URL,
                    json=_ollama_chat_payload(payload, stream=True),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            message = chunk.get("message") or {}
                            if message.get("thinking") and not message.get("content"):
                                message["content"] = message.get("thinking")
                                chunk["message"] = message
                                chunk["thinking_only"] = True
                            yield json.dumps(chunk) + "\n"
                        except json.JSONDecodeError:
                            yield f"{line}\n"
        except httpx.TimeoutException:
            yield json.dumps({"error": "Ollama request timed out"}) + "\n"
        except httpx.HTTPStatusError as exc:
            yield json.dumps({"error": f"Ollama returned HTTP {exc.response.status_code}"}) + "\n"
        except httpx.HTTPError:
            yield json.dumps({"error": "Could not connect to Ollama"}) + "\n"

    return StreamingResponse(stream_ollama(), media_type="application/x-ndjson")
