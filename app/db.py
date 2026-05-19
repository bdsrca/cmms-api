"""SQLite connection helpers and shared runtime paths."""

import sqlite3
import threading
from pathlib import Path
from typing import Any


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
