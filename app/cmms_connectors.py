"""CMMS connector configuration and controlled push helpers."""

from __future__ import annotations

import json
import base64
import hashlib
import hmac
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .db import DATA_DIR, db_execute, db_fetchall, db_fetchone, now_text


CONNECTOR_SECRET_PREFIX = "enc:v1:"
CONNECTOR_SECRET_KEY_FILE = DATA_DIR / "connector_secret.key"


def connector_secret_key() -> bytes:
    if CONNECTOR_SECRET_KEY_FILE.exists():
        return base64.urlsafe_b64decode(CONNECTOR_SECRET_KEY_FILE.read_bytes())
    key = secrets.token_bytes(32)
    CONNECTOR_SECRET_KEY_FILE.parent.mkdir(exist_ok=True)
    CONNECTOR_SECRET_KEY_FILE.write_bytes(base64.urlsafe_b64encode(key))
    return key


def secret_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        blocks.append(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return b"".join(blocks)[:length]


def protect_secret(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith(CONNECTOR_SECRET_PREFIX):
        return text
    key = connector_secret_key()
    nonce = secrets.token_bytes(16)
    plaintext = text.encode("utf-8")
    stream = secret_keystream(key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return CONNECTOR_SECRET_PREFIX + ".".join(
        base64.urlsafe_b64encode(part).decode("ascii")
        for part in (nonce, ciphertext, tag)
    )


def reveal_secret(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith(CONNECTOR_SECRET_PREFIX):
        return text
    try:
        nonce_text, ciphertext_text, tag_text = text.removeprefix(CONNECTOR_SECRET_PREFIX).split(".", 2)
        nonce = base64.urlsafe_b64decode(nonce_text.encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(ciphertext_text.encode("ascii"))
        tag = base64.urlsafe_b64decode(tag_text.encode("ascii"))
    except Exception:
        return ""
    key = connector_secret_key()
    expected_tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        return ""
    stream = secret_keystream(key, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream))
    return plaintext.decode("utf-8", errors="replace")


def migrate_plaintext_connector_secrets() -> None:
    rows = db_fetchall(
        """
        SELECT environment_code, secret_value
        FROM cmms_connectors
        WHERE secret_value IS NOT NULL AND secret_value != ''
        """
    )
    for row in rows:
        secret_value = str(row["secret_value"] or "")
        if secret_value.startswith(CONNECTOR_SECRET_PREFIX):
            continue
        db_execute(
            "UPDATE cmms_connectors SET secret_value = ?, updated_at = ? WHERE environment_code = ?",
            (protect_secret(secret_value), now_text(), row["environment_code"]),
        )


def normalize_environment_code(environment_code: str) -> str:
    return str(environment_code or "").strip().upper()


def normalize_auth_type(auth_type: Any) -> str:
    value = str(auth_type or "bearer").strip().lower()
    if value not in {"bearer", "header"}:
        raise ValueError("auth_type must be bearer or header")
    return value


def normalize_http_method(method: Any) -> str:
    value = str(method or "POST").strip().upper()
    if value not in {"POST", "PUT", "PATCH"}:
        raise ValueError("http_method must be POST, PUT, or PATCH")
    return value


def parse_success_status_codes(value: Any) -> set[int]:
    if value is None or value == "":
        return {200, 201, 202}
    if isinstance(value, (list, tuple, set)):
        parts = value
    else:
        parts = str(value).replace(";", ",").split(",")
    codes: set[int] = set()
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        code = int(text)
        if code < 100 or code > 599:
            raise ValueError("success_status_codes must contain HTTP status codes")
        codes.add(code)
    return codes or {200, 201, 202}


def success_status_codes_text(value: Any) -> str:
    return ",".join(str(code) for code in sorted(parse_success_status_codes(value)))


FORBIDDEN_STATIC_HEADERS = {"authorization", "proxy-authorization", "x-api-key"}


def normalize_static_headers(value: Any) -> dict[str, str]:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("static_headers must be an object") from exc
    if not isinstance(value, dict):
        raise ValueError("static_headers must be an object")
    headers: dict[str, str] = {}
    for key, raw in value.items():
        name = str(key or "").strip()
        if not name:
            continue
        if name.casefold() in FORBIDDEN_STATIC_HEADERS:
            raise ValueError("static_headers cannot include auth headers")
        headers[name] = str(raw or "").strip()
    return headers


def static_headers_json(value: Any) -> str | None:
    headers = normalize_static_headers(value)
    return json.dumps(headers, sort_keys=True) if headers else None


def connector_static_headers(connector: dict[str, Any]) -> dict[str, str]:
    return normalize_static_headers(connector.get("static_headers_json"))


def normalize_optional_text(value: Any, max_length: int = 240) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


def get_cmms_connector(environment_code: str) -> dict[str, Any] | None:
    env_code = normalize_environment_code(environment_code)
    row = db_fetchone("SELECT * FROM cmms_connectors WHERE environment_code = ?", (env_code,))
    return dict(row) if row else None


def upsert_cmms_connector(environment_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    env_code = normalize_environment_code(environment_code)
    existing = get_cmms_connector(env_code)
    now = now_text()
    auth_type = normalize_auth_type(payload.get("auth_type") if payload.get("auth_type") is not None else (existing or {}).get("auth_type"))
    secret_value = payload.get("secret_value")
    if secret_value is None and existing:
        protected_secret = protect_secret(existing.get("secret_value"))
    else:
        protected_secret = protect_secret(secret_value)
    auth_header_name = payload.get("auth_header_name")
    if auth_header_name is None and existing:
        auth_header_name = existing.get("auth_header_name")
    endpoint_url = payload.get("endpoint_url")
    if endpoint_url is None and existing:
        endpoint_url = existing.get("endpoint_url")
    timeout_seconds = int(payload.get("timeout_seconds") if payload.get("timeout_seconds") is not None else (existing or {}).get("timeout_seconds", 5))
    http_method = normalize_http_method(payload.get("http_method") if payload.get("http_method") is not None else (existing or {}).get("http_method"))
    success_codes = success_status_codes_text(payload.get("success_status_codes") if payload.get("success_status_codes") is not None else (existing or {}).get("success_status_codes"))
    static_headers = static_headers_json(payload.get("static_headers") if payload.get("static_headers") is not None else (existing or {}).get("static_headers_json"))
    external_id_path = normalize_optional_text(payload.get("external_id_path") if payload.get("external_id_path") is not None else (existing or {}).get("external_id_path"), 160)
    payload_root_key = normalize_optional_text(payload.get("payload_root_key") if payload.get("payload_root_key") is not None else (existing or {}).get("payload_root_key"), 80)
    auto_push_note = normalize_optional_text(payload.get("auto_push_note") if payload.get("auto_push_note") is not None else (existing or {}).get("auto_push_note"), 240)

    db_execute(
        """
        INSERT INTO cmms_connectors (
            environment_code, enabled, auto_push_enabled, endpoint_url, auth_type,
            auth_header_name, secret_value, timeout_seconds, http_method,
            success_status_codes, external_id_path, dry_run_enabled,
            require_metadata_review, static_headers_json, payload_root_key,
            auto_push_note, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(environment_code) DO UPDATE SET
            enabled = excluded.enabled,
            auto_push_enabled = excluded.auto_push_enabled,
            endpoint_url = excluded.endpoint_url,
            auth_type = excluded.auth_type,
            auth_header_name = excluded.auth_header_name,
            secret_value = excluded.secret_value,
            timeout_seconds = excluded.timeout_seconds,
            http_method = excluded.http_method,
            success_status_codes = excluded.success_status_codes,
            external_id_path = excluded.external_id_path,
            dry_run_enabled = excluded.dry_run_enabled,
            require_metadata_review = excluded.require_metadata_review,
            static_headers_json = excluded.static_headers_json,
            payload_root_key = excluded.payload_root_key,
            auto_push_note = excluded.auto_push_note,
            updated_at = excluded.updated_at
        """,
        (
            env_code,
            1 if payload.get("enabled", (existing or {}).get("enabled", False)) else 0,
            1 if payload.get("auto_push_enabled", (existing or {}).get("auto_push_enabled", False)) else 0,
            str(endpoint_url or "").strip() or None,
            auth_type,
            str(auth_header_name or "").strip() or None,
            protected_secret,
            timeout_seconds,
            http_method,
            success_codes,
            external_id_path,
            1 if payload.get("dry_run_enabled", (existing or {}).get("dry_run_enabled", False)) else 0,
            1 if payload.get("require_metadata_review", (existing or {}).get("require_metadata_review", False)) else 0,
            static_headers,
            payload_root_key,
            auto_push_note,
            (existing or {}).get("created_at", now),
            now,
        ),
    )
    connector = get_cmms_connector(env_code)
    if connector is None:
        raise RuntimeError("CMMS connector was not saved")
    return connector


def public_cmms_connector(connector: dict[str, Any] | None) -> dict[str, Any]:
    if not connector:
        return {
            "configured": False,
            "secret_configured": False,
        }
    return {
        "configured": True,
        "environment_code": connector.get("environment_code"),
        "enabled": bool(connector.get("enabled")),
        "auto_push_enabled": bool(connector.get("auto_push_enabled")),
        "endpoint_url": connector.get("endpoint_url"),
        "auth_type": connector.get("auth_type") or "bearer",
        "auth_header_name": connector.get("auth_header_name"),
        "timeout_seconds": connector.get("timeout_seconds"),
        "http_method": connector.get("http_method") or "POST",
        "success_status_codes": connector.get("success_status_codes") or "200,201,202",
        "external_id_path": connector.get("external_id_path"),
        "dry_run_enabled": bool(connector.get("dry_run_enabled")),
        "require_metadata_review": bool(connector.get("require_metadata_review")),
        "static_headers": connector_static_headers(connector),
        "payload_root_key": connector.get("payload_root_key"),
        "auto_push_note": connector.get("auto_push_note"),
        "secret_configured": bool(connector.get("secret_value")),
        "created_at": connector.get("created_at"),
        "updated_at": connector.get("updated_at"),
    }


def build_auth_headers(connector: dict[str, Any]) -> dict[str, str]:
    secret = reveal_secret(connector.get("secret_value"))
    if not secret:
        return {}
    auth_type = normalize_auth_type(connector.get("auth_type"))
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {secret}"}
    header_name = str(connector.get("auth_header_name") or "").strip()
    if not header_name:
        raise ValueError("auth_header_name is required for header auth")
    return {header_name: secret}


def endpoint_is_allowed(endpoint_url: str | None) -> bool:
    parsed = urllib.parse.urlparse(str(endpoint_url or ""))
    if parsed.scheme == "https" and parsed.netloc:
        return True
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    return False


def cmms_push_gate(connector: dict[str, Any] | None, context: dict[str, Any], payload: dict[str, Any] | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not connector:
        return "skipped", ["connector_not_configured"]
    if not connector.get("enabled"):
        return "skipped", ["connector_disabled"]
    if not connector.get("auto_push_enabled"):
        return "skipped", ["auto_push_disabled"]
    if not connector.get("endpoint_url"):
        reasons.append("endpoint_url_required")
    elif not endpoint_is_allowed(connector.get("endpoint_url")):
        reasons.append("endpoint_must_be_https_or_localhost")
    if not connector.get("secret_value"):
        reasons.append("secret_required")
    if not payload:
        reasons.append("payload_required")
    if not context.get("contract_valid"):
        reasons.append("contract_invalid")
    if not context.get("ai_validation_valid"):
        reasons.append("ai_validation_invalid")
    if not context.get("can_create_work_order"):
        reasons.append("cannot_create_work_order")
    if context.get("human_review_required"):
        reasons.append("human_review_required")
    if context.get("review_passed") is not True:
        reasons.append("review_not_passed")
    if context.get("fast_mode") and connector and not connector.get("dry_run_enabled"):
        reasons.append("full_review_required_for_live_push")
    if connector.get("require_metadata_review") and not context.get("metadata_reviewed"):
        reasons.append("metadata_review_required")
    if context.get("handoff_status") != "ready":
        reasons.append("handoff_not_ready")
    return ("blocked" if reasons else "allowed", reasons)


def sanitize_message(message: Any, connector: dict[str, Any] | None = None) -> str:
    text = str(message or "").replace("\r", " ").replace("\n", " ").strip()
    if connector and connector.get("secret_value"):
        secret = reveal_secret(connector.get("secret_value"))
        if secret:
            text = text.replace(secret, "[secret]")
    return text[:240]


def default_cmms_sender(
    *,
    endpoint_url: str,
    http_method: str,
    headers: dict[str, str],
    json_payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(json_payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint_url,
        data=body,
        headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
        method=http_method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = None
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = None
            return {"status_code": response.status, "json": parsed, "text": raw}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {"status_code": exc.code, "text": raw}
    except Exception as exc:  # pragma: no cover - exercised through fake sender tests.
        return {"status_code": None, "text": str(exc)}


def value_at_path(data: Any, path: str | None) -> Any:
    current = data
    for part in str(path or "").split("."):
        key = part.strip()
        if not key:
            continue
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def external_reference_from_response(response_json: Any, path: str | None = None) -> str | None:
    if not isinstance(response_json, dict):
        return None
    if path:
        value = value_at_path(response_json, path)
        if value:
            return str(value)
    for key in ("id", "reference", "work_order_id", "workOrderId", "number"):
        value = response_json.get(key)
        if value:
            return str(value)
    return None


def connector_payload(connector: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    root_key = str(connector.get("payload_root_key") or "").strip()
    return {root_key: payload} if root_key else payload


def record_cmms_push_event(environment_code: str, context: dict[str, Any], result: dict[str, Any]) -> None:
    db_execute(
        """
        INSERT INTO cmms_push_events (
            created_at, run_id, environment_code, status, blocked_reasons_json,
            status_code, external_reference, message, connector_enabled, auto_push_enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_text(),
            normalize_optional_text(context.get("run_id"), 120),
            normalize_environment_code(environment_code),
            str(result.get("status") or "unknown"),
            json.dumps(result.get("blocked_reasons") or []),
            result.get("status_code") if isinstance(result.get("status_code"), int) else None,
            normalize_optional_text(result.get("external_reference"), 160),
            normalize_optional_text(result.get("message"), 240),
            1 if result.get("connector_enabled") else 0,
            1 if result.get("auto_push_enabled") else 0,
        ),
    )


def public_cmms_push_event(row: Any) -> dict[str, Any]:
    event = dict(row)
    try:
        blocked_reasons = json.loads(event.get("blocked_reasons_json") or "[]")
    except json.JSONDecodeError:
        blocked_reasons = []
    return {
        "id": event.get("id"),
        "created_at": event.get("created_at"),
        "run_id": event.get("run_id"),
        "environment_code": event.get("environment_code"),
        "status": event.get("status"),
        "blocked_reasons": blocked_reasons if isinstance(blocked_reasons, list) else [],
        "status_code": event.get("status_code"),
        "external_reference": event.get("external_reference"),
        "message": event.get("message"),
        "connector_enabled": bool(event.get("connector_enabled")),
        "auto_push_enabled": bool(event.get("auto_push_enabled")),
    }


def list_cmms_push_events(environment_code: str, limit: int = 25) -> list[dict[str, Any]]:
    rows = db_fetchall(
        """
        SELECT * FROM cmms_push_events
        WHERE environment_code = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (normalize_environment_code(environment_code), max(1, min(int(limit or 25), 100))),
    )
    return [public_cmms_push_event(row) for row in rows]


def probe_cmms_connector(environment_code: str, sender: Any = None) -> dict[str, Any]:
    env_code = normalize_environment_code(environment_code)
    connector = get_cmms_connector(env_code)
    result = {
        "status": "blocked",
        "probe": True,
        "environment_code": env_code,
        "connector_enabled": bool(connector and connector.get("enabled")),
        "auto_push_enabled": bool(connector and connector.get("auto_push_enabled")),
        "blocked_reasons": [],
    }
    reasons: list[str] = []
    if not connector:
        reasons.append("connector_not_configured")
    elif not connector.get("enabled"):
        reasons.append("connector_disabled")
    if connector and not connector.get("dry_run_enabled"):
        reasons.append("dry_run_required_for_probe")
    if connector and not connector.get("endpoint_url"):
        reasons.append("endpoint_url_required")
    elif connector and not endpoint_is_allowed(connector.get("endpoint_url")):
        reasons.append("endpoint_must_be_https_or_localhost")
    if connector and not connector.get("secret_value"):
        reasons.append("secret_required")
    if reasons:
        result["blocked_reasons"] = reasons
        record_cmms_push_event(env_code, {"run_id": "manual-probe"}, result)
        return result

    probe_payload = {
        "schema": "cmms_connector_probe_v1",
        "probe": True,
        "dry_run": True,
        "summary": "CMMS connector probe",
        "source": "local-cmms-llm-api",
    }
    sender = sender or default_cmms_sender
    try:
        response = sender(
            endpoint_url=str(connector.get("endpoint_url")),
            http_method=normalize_http_method(connector.get("http_method")),
            headers={**connector_static_headers(connector), **build_auth_headers(connector)},
            json_payload=connector_payload(connector, probe_payload),
            timeout_seconds=int(connector.get("timeout_seconds") or 5),
        )
    except Exception as exc:
        failed = {**result, "status": "failed", "message": sanitize_message(exc, connector)}
        record_cmms_push_event(env_code, {"run_id": "manual-probe"}, failed)
        return failed

    status_code = response.get("status_code")
    response_json = response.get("json")
    message = ""
    if isinstance(response_json, dict):
        message = str(response_json.get("message") or response_json.get("status") or "")
    if not message:
        message = sanitize_message(response.get("text"), connector)
    sent = isinstance(status_code, int) and status_code in parse_success_status_codes(connector.get("success_status_codes"))
    probe_result = {
        **result,
        "status": "sent" if sent else "failed",
        "blocked_reasons": [],
        "status_code": status_code,
        "external_reference": external_reference_from_response(response_json, connector.get("external_id_path")),
        "message": sanitize_message(message, connector),
    }
    record_cmms_push_event(env_code, {"run_id": "manual-probe"}, probe_result)
    return probe_result


def auto_push_cmms_payload(
    environment_code: str,
    payload: dict[str, Any] | None,
    context: dict[str, Any],
    sender: Any = None,
) -> dict[str, Any]:
    connector = get_cmms_connector(environment_code)
    gate_status, reasons = cmms_push_gate(connector, context, payload)
    result = {
        "status": "blocked" if gate_status == "allowed" else gate_status,
        "auto_push_enabled": bool(connector and connector.get("auto_push_enabled")),
        "connector_enabled": bool(connector and connector.get("enabled")),
        "environment_code": normalize_environment_code(environment_code),
        "blocked_reasons": reasons,
        "idempotency_key": normalize_optional_text(context.get("idempotency_key"), 180),
    }
    def finish(push_result: dict[str, Any]) -> dict[str, Any]:
        record_cmms_push_event(environment_code, context, push_result)
        return push_result

    if gate_status != "allowed":
        return finish(result)
    if connector and connector.get("dry_run_enabled"):
        return finish({
            **result,
            "status": "dry_run",
            "blocked_reasons": [],
            "dry_run_enabled": True,
            "http_method": connector.get("http_method") or "POST",
            "endpoint_url": connector.get("endpoint_url"),
        })

    sender = sender or default_cmms_sender
    try:
        headers = {**connector_static_headers(connector or {}), **build_auth_headers(connector or {})}
        if result.get("idempotency_key"):
            headers.setdefault("Idempotency-Key", str(result["idempotency_key"]))
        outgoing_payload = connector_payload(connector or {}, payload or {})
        response = sender(
            endpoint_url=str(connector.get("endpoint_url")),
            http_method=normalize_http_method(connector.get("http_method")),
            headers=headers,
            json_payload=outgoing_payload,
            timeout_seconds=int(connector.get("timeout_seconds") or 5),
        )
    except Exception as exc:
        return finish({**result, "status": "failed", "message": sanitize_message(exc, connector)})

    status_code = response.get("status_code")
    response_json = response.get("json")
    message = ""
    if isinstance(response_json, dict):
        message = str(response_json.get("message") or response_json.get("status") or "")
    if not message:
        message = sanitize_message(response.get("text"), connector)
    sent = isinstance(status_code, int) and status_code in parse_success_status_codes(connector.get("success_status_codes"))
    return finish({
        **result,
        "status": "sent" if sent else "failed",
        "blocked_reasons": [],
        "status_code": status_code,
        "external_reference": external_reference_from_response(response_json, connector.get("external_id_path")),
        "message": sanitize_message(message, connector),
    })
