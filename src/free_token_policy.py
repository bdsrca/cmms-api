"""Public-safe free token policy example.

The module is intentionally small. It demonstrates the behavior a real API should keep:
hashed token storage, scopes, environment binding, quotas, expiry, and revocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Iterable


@dataclass
class FreeToken:
    token_id: str
    prefix: str
    secret_hash: str
    environment_code: str
    scopes: set[str]
    daily_quota: int
    monthly_quota: int
    expires_at: datetime
    status: str = "active"
    daily_used: int = 0
    monthly_used: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def issue_free_token(
    *,
    environment_code: str,
    scopes: Iterable[str],
    days_valid: int = 14,
    daily_quota: int = 100,
    monthly_quota: int = 1000,
) -> tuple[str, FreeToken]:
    """Issue a token and return the raw value once plus the stored record."""

    prefix = "cmms_free_" + secrets.token_hex(3)
    raw_secret = secrets.token_urlsafe(28)
    raw_token = f"{prefix}.{raw_secret}"
    token = FreeToken(
        token_id=secrets.token_hex(8),
        prefix=prefix,
        secret_hash=_hash_secret(raw_secret),
        environment_code=environment_code,
        scopes=set(scopes),
        daily_quota=daily_quota,
        monthly_quota=monthly_quota,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days_valid),
    )
    return raw_token, token


def verify_token(raw_token: str, token: FreeToken, *, scope: str, environment_code: str) -> tuple[bool, str]:
    """Verify one raw token against one stored token record."""

    if "." not in raw_token:
        return False, "malformed_token"
    prefix, secret = raw_token.split(".", 1)
    if prefix != token.prefix:
        return False, "prefix_mismatch"
    if _hash_secret(secret) != token.secret_hash:
        return False, "secret_mismatch"
    if token.status != "active":
        return False, f"token_{token.status}"
    if datetime.now(timezone.utc) >= token.expires_at:
        return False, "token_expired"
    if environment_code != token.environment_code:
        return False, "environment_not_allowed"
    if scope not in token.scopes:
        return False, "scope_not_allowed"
    if token.daily_used >= token.daily_quota:
        return False, "daily_quota_exceeded"
    if token.monthly_used >= token.monthly_quota:
        return False, "monthly_quota_exceeded"
    return True, "ok"


def consume_token(token: FreeToken) -> None:
    token.daily_used += 1
    token.monthly_used += 1


def revoke_token(token: FreeToken) -> None:
    token.status = "revoked"
