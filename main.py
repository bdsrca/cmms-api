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
from pathlib import Path
from typing import Any

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


MODEL_NAME = "qwen3:8b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
SERVICE_NAME = "local-cmms-llm-api"
ADVISORY_WARNING = "Advisory mode only. No CMMS write-back was performed."
SESSION_COOKIE = "cmms_portal_session"
SESSION_TTL_SECONDS = 8 * 60 * 60

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_FILE = DATA_DIR / "portal.db"
LOG_FILE = LOG_DIR / "cmms-llm-api.log"
API_KEYS_JSON = BASE_DIR / "api_keys.json"
DB_LOCK = threading.Lock()
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
    endpoint: str | None = None
    environment_code: str | None = None
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


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def db_execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with DB_LOCK:
        with db_connect() as conn:
            conn.execute(sql, params)
            conn.commit()


def db_fetchone(sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with DB_LOCK:
        with db_connect() as conn:
            return conn.execute(sql, params).fetchone()


def db_fetchall(sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with DB_LOCK:
        with db_connect() as conn:
            return conn.execute(sql, params).fetchall()


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
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
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


async def call_ollama(messages: list[dict[str, str]], timeout: int = 120) -> str:
    payload = {"model": MODEL_NAME, "messages": messages, "stream": False}
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
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: var(--text); background: var(--bg); }
    .login { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #243642, #0f6cbd); }
    .login-card { width: min(420px, calc(100% - 32px)); background: #fff; border-radius: 2px; box-shadow: 0 18px 42px rgba(0,0,0,.28); padding: 28px; }
    .login-card h1 { margin: 0 0 8px; font-size: 24px; }
    .login-card p { margin: 0 0 22px; color: var(--muted); }
    label { display: block; font-size: 12px; font-weight: 600; margin: 12px 0 5px; }
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
    .contracts-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(420px, 520px); gap: 14px; }
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
      me: null, page: "dashboard", envs: [], keys: [], output: {}, selectedEnv: "DEFAULT",
      envTab: "codes", selectedCategory: "buildings", selectedCode: null, codeData: null, validationRules: [],
      inputMode: "text", recognition: null, voiceSupported: null, voiceBaseTranscript: "", voiceFinalTranscript: "",
      voiceStopping: false, voiceStatus: "Idle"
    };
    const menu = [
      ["dashboard","Dashboard",false],["test","Test Console",false],["builder","API Call Builder",false],
      ["environments","Environments",true],["contracts","AI Output Contracts",true],["keys","API Keys",true],
      ["users","Users",true],["logs","Logs",false],["reports","Reports",false],["kb","Knowledge Base",false],
      ["remote","Remote Access",true],["system","System",true]
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
      const health = await api("/health").catch(() => null);
      $("healthText").textContent = health ? `${health.service} / ${health.model}` : "API offline";
    }
    function renderNav() {
      $("nav").innerHTML = menu.map(([id,label,admin]) => {
        if (admin && state.me.role !== "admin") return "";
        return `<button class="${state.page===id?'active':''} ${admin?'admin-only':''}" onclick="show('${id}')">${label}</button>`;
      }).join("");
    }
    function pageShell(title, html) { $("pageTitle").textContent = title; $("pageActions").innerHTML = ""; $("page").innerHTML = html; renderNav(); }
    function envOptions() { return state.envs.map(e => `<option value="${e.environment_code}">${e.environment_code} - ${e.name}</option>`).join(""); }
    function show(id) {
      state.page = id; renderNav();
      const handlers = { dashboard, test, builder, environments, contracts, keys, users, logs, reports, kb, remote, system };
      handlers[id]();
    }
    function dashboard() {
      pageShell("Dashboard", `<div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${state.envs.length}</div><div class="muted">Environments</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${state.keys.length}</div><div class="muted">API keys</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${state.me.role}</div><div class="muted">Current role</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">qwen3:8b</div><div class="muted">Local model</div></div></div>
        <div class="card span-12"><h2>Safety posture</h2><div class="card-body">Advisory mode only. No CMMS write-back, work order creation, approval, or email sending occurs.</div></div>
      </div>`);
    }
    function test() {
      pageShell("Test Console", `<div class="grid">
        <div class="card playground span-4"><div class="playground-header"><div><div class="playground-title">Run console</div><div class="playground-subtitle">Text and voice share one editable input.</div></div><span class="pill">API</span></div><div class="card-body stack">
          <label>API key</label><input id="tKey" type="password" value="my-secret-key">
          <label>Mode</label><select id="tEndpoint" onchange="renderTestModeHelp()"><option value="cmms-intake">CMMS Intake</option><option value="cmms-assistant">CMMS Assistant Chat</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select>
          <label>Environment</label><select id="tEnv">${envOptions()}</select>
          <div id="testModeHelp" class="notice"></div>
          <div id="testInputPanel"></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Response</div><div class="playground-subtitle" id="inputSourceLabel">Input source: none</div></div><span id="runStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="tReadiness" class="readiness"><strong>Work order readiness</strong><div class="muted">Run CMMS Intake to evaluate whether enough validated information exists for a human-controlled workflow.</div></div>
            <div class="result-grid">
              <div class="ai-panel"><h3>Contract Validation</h3><div id="tContract"><span class="muted">Run a request to see contract validation.</span></div></div>
              <div class="ai-panel"><h3>Environment Validation</h3><div id="tValidation"><span class="muted">Run a request to see environment validation.</span></div></div>
            </div>
            <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Extracted JSON</strong><span class="muted">No raw audio is stored</span></div><pre id="tOut">{}</pre></div>
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
          <div class="button-grid"><button onclick="runTest('text')">Run</button><button class="secondary" onclick="clearVoiceTranscript()">Clear</button></div>
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
            <button class="secondary" onclick="clearVoiceTranscript()">Clear Transcript</button>
            <button onclick="sendVoiceToApi()">Send to API</button>
          </div>
          <label><input id="voiceAutoSend" type="checkbox" style="width:auto"> Auto-send after speech ends</label>
          <div class="row"><button class="secondary" onclick="setVoiceSample('en')">English sample</button><button class="secondary" onclick="setVoiceSample('zh')">Chinese sample</button><button class="secondary" onclick="setVoiceSample('fr')">French sample</button></div>
          <div id="voiceMessage" class="muted">Speech recognition is handled by the browser. This app does not store audio. Review the transcript before sending.</div>
        </div>`;
    }
    function renderTestModeHelp() {
      if (!$("testModeHelp")) return;
      const ep = $("tEndpoint")?.value || "cmms-intake";
      const copy = {
        "cmms-intake": "Controlled extraction workflow: contract validation, environment validation, readiness, and advisory drafts.",
        "cmms-assistant": "Controlled CMMS assistant chat. It can discuss intake, validation, API usage, and drafts, but cannot create work orders or write to CMMS.",
        "extract-work-order-fields": "Field extraction only. Useful for debugging request type, building, room, priority, and missing fields.",
        "summarize-work-order": "One-sentence work request summary. No readiness validation."
      };
      $("testModeHelp").textContent = copy[ep] || copy["cmms-intake"];
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
      recognition.onstart = () => setVoiceStatus("Listening", "Listening. You can stop, edit the transcript, then send it to the API.");
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
        setVoiceStatus("Listening");
      };
      recognition.onend = () => {
        state.recognition = null;
        const endedWithError = state.voiceStatus === "Error";
        if (!endedWithError) setVoiceStatus("Idle", state.voiceStopping ? "Listening stopped. Review the transcript before sending." : "Speech recognition ended. Review the transcript before sending.");
        if (!endedWithError && $("voiceAutoSend")?.checked && transcriptValue()) sendVoiceToApi();
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
    async function sendVoiceToApi() {
      if (!transcriptValue()) {
        setVoiceStatus("Error", "Transcript is empty. Speak, type, or choose a sample before sending.");
        return;
      }
      await runTest("voice_transcript");
    }
    async function runTest(sourceOverride) {
      const ep = $("tEndpoint").value;
      const source = sourceOverride || "text";
      const text = transcriptValue();
      if (!text) {
        const message = source === "voice_transcript" ? "Transcript is empty. Speak, type, or choose a sample before sending." : "Text is required.";
        if (source === "voice_transcript") setVoiceStatus("Error", message);
        $("tOut").textContent = JSON.stringify({ error: message }, null, 2);
        return;
      }
      const body = { text, environment_code: $("tEnv").value };
      if (source === "voice_transcript") body.source = "voice_transcript";
      try {
        if ($("runStatus")) $("runStatus").textContent = "Running";
        const data = await api(`/api/ai/${ep}`, { method: "POST", headers: { "x-api-key": $("tKey").value }, body: JSON.stringify(body) });
        if ($("inputSourceLabel")) $("inputSourceLabel").textContent = source === "voice_transcript" ? "Input source: voice transcript" : "Input source: text";
        if ($("runStatus")) $("runStatus").textContent = "Complete";
        $("tOut").textContent = JSON.stringify(data, null, 2);
        renderContractValidation(data.contract);
        renderTestValidation(data.ai_validation);
        renderReadiness(data);
        if (source === "voice_transcript") setVoiceStatus("Idle", "Voice transcript sent to the API.");
      } catch (e) {
        if ($("runStatus")) $("runStatus").textContent = "Error";
        if (source === "voice_transcript") setVoiceStatus("Error", e.message || "API call failed.");
        $("tOut").textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
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

    function issueList(items) {
      if (!items || !items.length) return '<p class="muted">None</p>';
      return `<ul>${items.map(i=>`<li><strong>${escapeHtml(i.field)}</strong>: ${escapeHtml(i.message)} <span class="muted">(${escapeHtml(i.value ?? "")})</span></li>`).join("")}</ul>`;
    }
    function builder() {
      const base = location.origin;
      pageShell("API Call Builder", `<div class="grid">
        <div class="card span-4"><h2>Inputs</h2><div class="card-body stack">
          <label>Base URL</label><input id="bBase" value="${base}">
          <label>API key</label><input id="bKey" value="cmms_your_generated_key">
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
          <div class="ai-panel ai-panel-dark"><pre id="bOut" class="code-output"></pre></div>
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
      $("bOut").textContent = `PowerShell:\n${ps}\n\ncurl:\n${curl}\n\nJSON body:\n${body}\n\nExpected response fields:\n${expectedFields(ep).join("\\n")}`;
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
        $("bOut").textContent = `${$("bOut").textContent}\n\nLive response:\n${JSON.stringify(data, null, 2)}`;
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
        <pre id="contractResult" style="min-height:160px">{}</pre>`;
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
      try { values = JSON.parse($("contractSample").value); } catch { $("contractResult").textContent = "Invalid sample JSON"; return; }
      const data = await api(`/api/admin/output-contracts/${id}/validate-sample`, { method: "POST", body: JSON.stringify({ values }) });
      $("contractResult").textContent = JSON.stringify(data, null, 2);
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
    async function logs() { const data = await api("/api/admin/logs?lines=220"); pageShell("Logs", `<div class="card"><h2>Runtime log</h2><pre>${data.lines.join("\n")}</pre></div>`); }
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
    summary = await call_ollama(summarize_prompt(payload.text))
    return SummaryResponse(summary=summary)


@app.post("/api/ai/cmms-assistant", response_model=AssistantResponse, dependencies=[Depends(require_api_key)])
async def cmms_assistant(request: Request, payload: TextRequest) -> AssistantResponse:
    if payload.environment_code:
        request.state.environment_code = payload.environment_code
    content = await call_ollama(assistant_prompt(payload.text))
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
    content = await call_ollama(extract_prompt(payload.text, valid_buildings, valid_priorities))
    data = parse_json_response(content)
    return validate_extracted_fields(data, valid_buildings, valid_priorities)


@app.post("/api/ai/cmms-intake", response_model=IntakeResponse, dependencies=[Depends(require_api_key)])
async def cmms_intake(request: Request, payload: ExtractFieldsRequest) -> IntakeResponse:
    valid_buildings, valid_priorities, env_code = resolve_validation_lists(payload)
    if env_code:
        request.state.environment_code = env_code
    classifier_data = parse_json_response(await call_ollama(classifier_prompt(payload.text)))
    extractor_data = parse_json_response(await call_ollama(field_extractor_prompt(payload.text, valid_buildings, valid_priorities)))
    request_type, confidence, fields, validation = validate_intake(
        classifier_data.get("request_type"),
        classifier_data.get("confidence"),
        extractor_data,
        valid_buildings,
        valid_priorities,
    )
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
    contract_validation = validate_output_contract("cmms-intake", result_payload)
    contract_block = {
        "version": contract_validation["contract_version"],
        "valid": contract_validation["valid"],
        "errors": contract_validation["errors"],
        "warnings": contract_validation["warnings"],
    }
    if env_code and contract_validation["valid"]:
        ai_validation = validate_ai_output(
            env_code,
            contract_validation["normalized_payload"],
        )
        ai_validation["enabled"] = True
        ai_validation["status"] = "completed"
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
    draft_data = parse_json_response(await call_ollama(draft_prompt(payload.text, request_type, fields, validation)))
    drafts = IntakeDrafts(
        draft_wo_description=str(draft_data.get("draft_wo_description") or fields.summary),
        internal_note=str(draft_data.get("internal_note") or "Validated intake. Ready for human review or controlled CMMS workflow."),
        client_reply=str(draft_data.get("client_reply") or "Thanks, we captured your request."),
    )
    return IntakeResponse(
        endpoint="cmms-intake",
        environment_code=env_code,
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
