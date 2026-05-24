"""SQLite connection helpers and shared runtime paths."""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_FILE = DATA_DIR / "portal.db"
LOG_FILE = LOG_DIR / "cmms-llm-api.log"
API_KEYS_JSON = BASE_DIR / "api_keys.json"
DB_LOCK = threading.Lock()

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


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


SCHEMA_STATEMENTS = [
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
        usage_count INTEGER NOT NULL DEFAULT 0,
        allowed_endpoints_json TEXT,
        allowed_environments_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS environments (
        environment_code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        default_workflow_mode TEXT NOT NULL DEFAULT 'fast',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cmms_connectors (
        environment_code TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 0,
        auto_push_enabled INTEGER NOT NULL DEFAULT 0,
        endpoint_url TEXT,
        auth_type TEXT NOT NULL DEFAULT 'bearer',
        auth_header_name TEXT,
        secret_value TEXT,
        timeout_seconds INTEGER NOT NULL DEFAULT 5,
        http_method TEXT NOT NULL DEFAULT 'POST',
        success_status_codes TEXT NOT NULL DEFAULT '200,201,202',
        external_id_path TEXT,
        dry_run_enabled INTEGER NOT NULL DEFAULT 0,
        require_metadata_review INTEGER NOT NULL DEFAULT 0,
        static_headers_json TEXT,
        payload_root_key TEXT,
        auto_push_note TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(environment_code) REFERENCES environments(environment_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cmms_push_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        run_id TEXT,
        environment_code TEXT NOT NULL,
        status TEXT NOT NULL,
        blocked_reasons_json TEXT,
        status_code INTEGER,
        external_reference TEXT,
        message TEXT,
        connector_enabled INTEGER NOT NULL DEFAULT 0,
        auto_push_enabled INTEGER NOT NULL DEFAULT 0
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
    """
    CREATE TABLE IF NOT EXISTS intake_metadata_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL UNIQUE,
        extracted_submission_json TEXT NOT NULL,
        extracted_request_json TEXT NOT NULL,
        reviewed_submission_json TEXT,
        reviewed_request_json TEXT,
        metadata_review_json TEXT,
        reviewed_by_user_id INTEGER,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_at ON workflow_runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_runs_endpoint ON workflow_runs(endpoint)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_runs_environment ON workflow_runs(environment_code)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_run_id ON workflow_run_steps(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_cmms_push_events_environment ON cmms_push_events(environment_code, id)",
    "CREATE INDEX IF NOT EXISTS idx_cmms_push_events_run_id ON cmms_push_events(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_intake_metadata_reviews_run_id ON intake_metadata_reviews(run_id)",
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


def ensure_schema_columns(conn: sqlite3.Connection) -> None:
    environment_columns = {row["name"] for row in conn.execute("PRAGMA table_info(environments)").fetchall()}
    environment_migrations = {
        "default_workflow_mode": "ALTER TABLE environments ADD COLUMN default_workflow_mode TEXT NOT NULL DEFAULT 'fast'",
    }
    for column, statement in environment_migrations.items():
        if column not in environment_columns:
            conn.execute(statement)
    conn.execute(
        "UPDATE environments SET default_workflow_mode = 'fast' WHERE default_workflow_mode IS NULL OR default_workflow_mode = ''"
    )
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
    cmms_columns = {row["name"] for row in conn.execute("PRAGMA table_info(cmms_connectors)").fetchall()}
    cmms_migrations = {
        "http_method": "ALTER TABLE cmms_connectors ADD COLUMN http_method TEXT NOT NULL DEFAULT 'POST'",
        "success_status_codes": "ALTER TABLE cmms_connectors ADD COLUMN success_status_codes TEXT NOT NULL DEFAULT '200,201,202'",
        "external_id_path": "ALTER TABLE cmms_connectors ADD COLUMN external_id_path TEXT",
        "dry_run_enabled": "ALTER TABLE cmms_connectors ADD COLUMN dry_run_enabled INTEGER NOT NULL DEFAULT 0",
        "require_metadata_review": "ALTER TABLE cmms_connectors ADD COLUMN require_metadata_review INTEGER NOT NULL DEFAULT 0",
        "static_headers_json": "ALTER TABLE cmms_connectors ADD COLUMN static_headers_json TEXT",
        "payload_root_key": "ALTER TABLE cmms_connectors ADD COLUMN payload_root_key TEXT",
        "auto_push_note": "ALTER TABLE cmms_connectors ADD COLUMN auto_push_note TEXT",
    }
    for column, statement in cmms_migrations.items():
        if column not in cmms_columns:
            conn.execute(statement)
    api_key_columns = {row["name"] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    api_key_migrations = {
        "allowed_endpoints_json": "ALTER TABLE api_keys ADD COLUMN allowed_endpoints_json TEXT",
        "allowed_environments_json": "ALTER TABLE api_keys ADD COLUMN allowed_environments_json TEXT",
    }
    for column, statement in api_key_migrations.items():
        if column not in api_key_columns:
            conn.execute(statement)


def init_db(seed_callbacks: list[Callable[[], None]] | None = None) -> None:
    with DB_LOCK:
        with db_connect() as conn:
            for statement in [*SCHEMA_STATEMENTS, *INDEX_STATEMENTS]:
                conn.execute(statement)
            ensure_schema_columns(conn)
            conn.commit()
    for callback in seed_callbacks or []:
        callback()
