"""Setup readiness checks and safe local backup helpers."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen

from . import db
from .config import MODEL_NAME, SERVICE_NAME


BACKUP_DIR = db.DATA_DIR / "backups"
BACKUP_DB_NAME = "portal.db"
MANIFEST_NAME = "manifest.json"
SETUP_STATUSES = {"passed", "warning", "failed", "not_checked"}
REQUIRED_DB_TABLES = {
    "users",
    "api_keys",
    "environments",
    "environment_validation_rules",
    "ai_output_contracts",
    "ai_prompt_versions",
    "settings",
}
BACKUP_EXCLUDED_ITEMS = [
    ".env",
    "api_keys.json",
    "logs/",
    "session cookies",
    "raw API key plaintext",
    "raw secrets",
    "generated runtime temp files",
]


def now_text() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def backup_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def setup_item(
    item_id: str,
    label: str,
    status: str,
    detail: str,
    recommended_action: str = "",
) -> dict[str, str]:
    if status not in SETUP_STATUSES:
        raise ValueError(f"Invalid setup status: {status}")
    return {
        "id": item_id,
        "label": label,
        "status": status,
        "detail": detail,
        "recommended_action": recommended_action,
    }


def _status_summary(items: list[dict[str, str]]) -> dict[str, int]:
    return {status: sum(1 for item in items if item["status"] == status) for status in sorted(SETUP_STATUSES)}


def _overall_status(items: list[dict[str, str]]) -> str:
    if any(item["status"] == "failed" for item in items):
        return "failed"
    if any(item["status"] in {"warning", "not_checked"} for item in items):
        return "warning"
    return "passed"


def _db_table_names() -> set[str]:
    uri = f"file:{db.DB_FILE}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def _db_count(sql: str, params: tuple[Any, ...] = ()) -> int:
    conn = sqlite3.connect(db.DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(sql, params).fetchone()
    finally:
        conn.close()
    if row is None:
        return 0
    return int(row["count"])


def _bool_from_count(sql: str, params: tuple[Any, ...] = ()) -> bool:
    return _db_count(sql, params) > 0


def _writable_directory(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path, prefix=".write-check-", delete=False, encoding="utf-8") as handle:
            handle.write("ok")
            temp_path = Path(handle.name)
        temp_path.unlink(missing_ok=True)
        return True, f"{path} is writable."
    except OSError as exc:
        return False, str(exc)


def ollama_tags_url() -> str:
    return "http://localhost:11434/api/tags"


def probe_ollama_tags() -> dict[str, Any]:
    try:
        with urlopen(ollama_tags_url(), timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"reachable": False, "models": [], "error": str(exc)}

    models = []
    for item in payload.get("models", []):
        if isinstance(item, dict):
            model_name = item.get("name") or item.get("model")
            if model_name:
                models.append(str(model_name))
    return {"reachable": True, "models": models, "error": None}


def _db_dependent_item(item_id: str, label: str, db_ready: bool) -> dict[str, str] | None:
    if db_ready:
        return None
    return setup_item(
        item_id,
        label,
        "not_checked",
        "SQLite DB is not initialized, so this check could not run.",
        "Initialize the local database and restart the API.",
    )


def build_setup_status(ollama_probe: Callable[[], dict[str, Any]] = probe_ollama_tags) -> dict[str, Any]:
    items: list[dict[str, str]] = [
        setup_item(
            "api_running",
            "Python/FastAPI app running",
            "passed",
            "This status endpoint was served by the local FastAPI app.",
        )
    ]

    db_ready = False
    if not db.DB_FILE.exists():
        items.append(
            setup_item(
                "sqlite_db_initialized",
                "SQLite DB initialized",
                "failed",
                f"SQLite DB was not found at {db.DB_FILE}.",
                "Start the API once so startup can initialize the database.",
            )
        )
    else:
        try:
            tables = _db_table_names()
            missing_tables = sorted(REQUIRED_DB_TABLES - tables)
            db_ready = not missing_tables
            items.append(
                setup_item(
                    "sqlite_db_initialized",
                    "SQLite DB initialized",
                    "passed" if db_ready else "failed",
                    "Required tables are present." if db_ready else f"Missing tables: {', '.join(missing_tables)}.",
                    "Run the app startup migration path by restarting the API." if missing_tables else "",
                )
            )
        except sqlite3.Error as exc:
            items.append(
                setup_item(
                    "sqlite_db_initialized",
                    "SQLite DB initialized",
                    "failed",
                    f"SQLite DB could not be read: {exc}.",
                    "Check file permissions and rerun database initialization.",
                )
            )

    db_checks = [
        (
            "admin_user_exists",
            "Admin user exists",
            "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND enabled = 1",
            (),
            "At least one enabled admin user is configured.",
            "Create or enable an admin user before handing this install to another operator.",
        ),
        (
            "default_environment_exists",
            "DEFAULT environment exists",
            "SELECT COUNT(*) AS count FROM environments WHERE environment_code = 'DEFAULT' AND enabled = 1",
            (),
            "The DEFAULT environment is present and enabled.",
            "Create or re-enable the DEFAULT environment.",
        ),
        (
            "enabled_api_key_exists",
            "At least one enabled API key exists",
            "SELECT COUNT(*) AS count FROM api_keys WHERE enabled = 1",
            (),
            "At least one generated API key is enabled.",
            "Create an enabled API key for controlled AI endpoint access.",
        ),
        (
            "required_validation_rule_exists",
            "At least one required validation rule exists",
            "SELECT COUNT(*) AS count FROM environment_validation_rules WHERE enabled = 1 AND required = 1",
            (),
            "At least one enabled validation rule is marked required.",
            "Reset or configure validation rules for the active environment.",
        ),
        (
            "active_prompt_versions_exist",
            "Active prompt versions exist",
            "SELECT COUNT(*) AS count FROM ai_prompt_versions WHERE status = 'active'",
            (),
            "At least one prompt version is active.",
            "Activate the required prompt versions before demo or handoff.",
        ),
        (
            "active_output_contract_exists",
            "Active output contract exists",
            "SELECT COUNT(*) AS count FROM ai_output_contracts WHERE status = 'active'",
            (),
            "At least one output contract is active.",
            "Activate an output contract before running advisory endpoints.",
        ),
    ]
    for item_id, label, sql, params, passed_detail, action in db_checks:
        skipped = _db_dependent_item(item_id, label, db_ready)
        if skipped:
            items.append(skipped)
            continue
        try:
            exists = _bool_from_count(sql, params)
            items.append(setup_item(item_id, label, "passed" if exists else "failed", passed_detail if exists else "No matching record was found.", action if not exists else ""))
        except sqlite3.Error as exc:
            items.append(setup_item(item_id, label, "failed", f"Check failed: {exc}.", "Check database permissions and schema."))

    llm_key_configured = bool(os.environ.get("LLM_API_KEY"))
    items.append(
        setup_item(
            "llm_api_key_configured",
            "LLM_API_KEY configured",
            "passed" if llm_key_configured else "failed",
            "LLM_API_KEY is set." if llm_key_configured else "LLM_API_KEY is not set.",
            "Set LLM_API_KEY in the local environment configuration." if not llm_key_configured else "",
        )
    )

    try:
        ollama = ollama_probe()
    except Exception as exc:  # defensive boundary for injected probes
        ollama = {"reachable": False, "models": [], "error": str(exc)}
    ollama_reachable = bool(ollama.get("reachable"))
    items.append(
        setup_item(
            "ollama_reachable",
            "Ollama reachable",
            "passed" if ollama_reachable else "warning",
            "Ollama responded to the local tags endpoint." if ollama_reachable else f"Ollama tags endpoint was not reachable: {ollama.get('error') or 'unknown error'}.",
            "Start Ollama locally before running live AI endpoint demos." if not ollama_reachable else "",
        )
    )
    if ollama_reachable:
        models = {str(name) for name in ollama.get("models", [])}
        model_available = MODEL_NAME in models
        items.append(
            setup_item(
                "qwen_model_available",
                f"{MODEL_NAME} model availability",
                "passed" if model_available else "warning",
                f"{MODEL_NAME} is available." if model_available else f"{MODEL_NAME} was not found in Ollama model tags.",
                f"Pull or install {MODEL_NAME} in Ollama before live model demos." if not model_available else "",
            )
        )
    else:
        items.append(
            setup_item(
                "qwen_model_available",
                f"{MODEL_NAME} model availability",
                "not_checked",
                "Ollama reachability failed, so model availability was not checked.",
                "Start Ollama and refresh setup checks.",
            )
        )

    logs_ok, logs_detail = _writable_directory(db.LOG_DIR)
    items.append(
        setup_item(
            "logs_directory_writable",
            "Logs directory writable",
            "passed" if logs_ok else "failed",
            logs_detail,
            "Fix local filesystem permissions for the logs directory." if not logs_ok else "",
        )
    )
    backup_ok, backup_detail = _writable_directory(BACKUP_DIR)
    items.append(
        setup_item(
            "backup_directory_writable",
            "Backup directory writable",
            "passed" if backup_ok else "failed",
            backup_detail,
            "Create the backup directory or fix local filesystem permissions." if not backup_ok else "",
        )
    )

    summary = _status_summary(items)
    return {
        "checked_at": now_text(),
        "overall_status": _overall_status(items),
        "summary": summary,
        "items": items,
        "backup_directory": str(BACKUP_DIR),
    }


def _public_count_manifest() -> dict[str, int]:
    if not db.DB_FILE.exists():
        return {}
    counts: dict[str, int] = {}
    safe_count_queries = {
        "users_total": "SELECT COUNT(*) AS count FROM users",
        "admin_users_enabled": "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND enabled = 1",
        "api_keys_enabled": "SELECT COUNT(*) AS count FROM api_keys WHERE enabled = 1",
        "environments_total": "SELECT COUNT(*) AS count FROM environments",
        "required_validation_rules_enabled": "SELECT COUNT(*) AS count FROM environment_validation_rules WHERE enabled = 1 AND required = 1",
        "active_prompt_versions": "SELECT COUNT(*) AS count FROM ai_prompt_versions WHERE status = 'active'",
        "active_output_contracts": "SELECT COUNT(*) AS count FROM ai_output_contracts WHERE status = 'active'",
    }
    for key, sql in safe_count_queries.items():
        try:
            counts[key] = _db_count(sql)
        except sqlite3.Error:
            counts[key] = 0
    return counts


def build_backup_manifest(backup_id: str, created_at: str, created_by: str | None = None) -> dict[str, Any]:
    counts = _public_count_manifest()
    try:
        default_environment_exists = _bool_from_count(
            "SELECT COUNT(*) AS count FROM environments WHERE environment_code = 'DEFAULT' AND enabled = 1"
        )
    except sqlite3.Error:
        default_environment_exists = False
    return {
        "backup_id": backup_id,
        "created_at": created_at,
        "created_by": created_by or "unknown",
        "service": SERVICE_NAME,
        "model": MODEL_NAME,
        "format_version": 1,
        "contents": [
            {"path": MANIFEST_NAME, "type": "public_safe_manifest"},
            {"path": BACKUP_DB_NAME, "type": "sqlite_db_copy"},
        ],
        "configuration": {
            "llm_api_key_configured": bool(os.environ.get("LLM_API_KEY")),
            "default_environment_exists": default_environment_exists,
            "enabled_api_key_count": counts.get("api_keys_enabled", 0),
            "active_prompt_version_count": counts.get("active_prompt_versions", 0),
            "active_output_contract_count": counts.get("active_output_contracts", 0),
        },
        "counts": counts,
        "excluded": BACKUP_EXCLUDED_ITEMS,
        "restore": {
            "mode": "preview_only",
            "destructive_restore_available": False,
        },
    }


def _copy_sqlite_database(destination: Path) -> None:
    if not db.DB_FILE.exists():
        raise FileNotFoundError(f"SQLite DB not found at {db.DB_FILE}")
    with db.DB_LOCK:
        source = sqlite3.connect(db.DB_FILE)
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()


def create_system_backup(created_by: str | None = None) -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    created_at = now_text()
    backup_id = f"backup_{backup_timestamp()}_{uuid.uuid4().hex[:8]}"
    archive_path = BACKUP_DIR / f"{backup_id}.zip"
    temp_db = BACKUP_DIR / f".{backup_id}.db.tmp"
    manifest = build_backup_manifest(backup_id, created_at, created_by)

    try:
        _copy_sqlite_database(temp_db)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))
            archive.write(temp_db, BACKUP_DB_NAME)
    finally:
        temp_db.unlink(missing_ok=True)

    return {
        "backup_id": backup_id,
        "created_at": created_at,
        "file_name": archive_path.name,
        "file_path": str(archive_path),
        "size_bytes": archive_path.stat().st_size,
        "manifest": manifest,
    }


def _read_manifest_from_archive(archive_path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            if MANIFEST_NAME not in archive.namelist():
                return {}
            return json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError):
        return {}


def list_system_backups() -> list[dict[str, Any]]:
    if not BACKUP_DIR.exists():
        return []
    backups: list[dict[str, Any]] = []
    for archive_path in sorted(BACKUP_DIR.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True):
        manifest = _read_manifest_from_archive(archive_path)
        backups.append(
            {
                "backup_id": manifest.get("backup_id", archive_path.stem),
                "created_at": manifest.get("created_at", ""),
                "file_name": archive_path.name,
                "file_path": str(archive_path),
                "size_bytes": archive_path.stat().st_size,
                "manifest": manifest,
            }
        )
    return backups


def _safe_backup_path(backup_id: str | None = None, file_name: str | None = None) -> Path:
    if not backup_id and not file_name:
        raise ValueError("backup_id or file_name is required")
    name = file_name or f"{backup_id}.zip"
    if not name or Path(name).name != name or not name.endswith(".zip"):
        raise ValueError("Backup file name must be a local .zip file name")
    root = BACKUP_DIR.resolve()
    candidate = (BACKUP_DIR / name).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Backup path must stay inside the backup directory")
    if not candidate.exists():
        raise FileNotFoundError(f"Backup not found: {name}")
    return candidate


def preview_system_restore(backup_id: str | None = None, file_name: str | None = None) -> dict[str, Any]:
    archive_path = _safe_backup_path(backup_id=backup_id, file_name=file_name)
    with zipfile.ZipFile(archive_path) as archive:
        contents = archive.namelist()
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8")) if MANIFEST_NAME in contents else {}

    warnings: list[str] = []
    if MANIFEST_NAME not in contents:
        warnings.append("Backup manifest is missing.")
    if BACKUP_DB_NAME not in contents:
        warnings.append("SQLite DB copy is missing.")
    unexpected = sorted(name for name in contents if name not in {MANIFEST_NAME, BACKUP_DB_NAME})
    if unexpected:
        warnings.append(f"Unexpected archive contents: {', '.join(unexpected)}.")

    return {
        "status": "preview_only",
        "restore_supported": False,
        "backup_id": manifest.get("backup_id", archive_path.stem),
        "file_name": archive_path.name,
        "contents": contents,
        "manifest": manifest,
        "warnings": warnings,
        "message": "Restore is preview-only in v1. No files or database records were changed.",
    }
