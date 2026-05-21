"""Portal authentication, password hashing, sessions, and role guards."""

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .db import db_execute, db_fetchone


SESSION_COOKIE = "cmms_portal_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
LOGIN_LOCK = threading.Lock()
LOGIN_FAILURES: dict[str, dict[str, Any]] = {}
LOGIN_WINDOW_SECONDS = 10 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5
DISALLOWED_ADMIN_PASSWORDS = {"change-this-password", "password", "admin", "admin123", "my-secret-key"}
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
logger = logging.getLogger("local-cmms-llm-api")


class AuthContext(BaseModel):
    key_id: str
    name: str
    is_admin: bool
    source: str


class PortalUser(BaseModel):
    user_id: int
    username: str
    role: str


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def login_user(payload: Any, request: Request, response: Response) -> dict[str, Any]:
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


def logout_user(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db_execute("DELETE FROM sessions WHERE token_hash = ?", (hash_text(token),))
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


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
