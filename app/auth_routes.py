"""Authentication and portal user administration routes."""

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .db import db_execute, db_fetchall, db_fetchone, now_text
from .security import PortalUser, current_admin, hash_password, login_user, logout_user


router = APIRouter()


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


@router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    return login_user(payload, request, response)


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    return logout_user(request, response)


@router.get("/api/admin/users")
async def list_users(user: PortalUser = Depends(current_admin)) -> list[dict[str, Any]]:
    rows = db_fetchall("SELECT user_id, username, role, enabled, created_at, last_login_at FROM users ORDER BY username")
    return [dict(row) for row in rows]


@router.post("/api/admin/users")
async def create_user(payload: UserCreateRequest, user: PortalUser = Depends(current_admin)) -> dict[str, Any]:
    try:
        db_execute(
            "INSERT INTO users (username, password_hash, role, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
            (payload.username.strip(), hash_password(payload.password), payload.role, now_text()),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Username already exists") from exc
    return {"status": "ok", "username": payload.username.strip()}


@router.patch("/api/admin/users/{user_id}")
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
