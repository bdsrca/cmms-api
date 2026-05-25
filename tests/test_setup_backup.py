import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.config import MODEL_NAME
from app.management_routes import build_management_router
from app.security import PortalUser, current_user, hash_text
from app import system_setup


def build_management_test_router() -> FastAPI:
    async def ollama_false() -> bool:
        return False

    app = FastAPI()
    app.include_router(
        build_management_router(
            require_local_control=lambda request: None,
            is_ollama_running=ollama_false,
            wait_for_ollama=ollama_false,
            start_ollama_process=lambda: None,
            stop_ollama_process=lambda: None,
            shutdown_process_later=lambda: None,
        )
    )
    return app


class SetupBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.tmp.name)
        self.db_file = root / "portal.db"
        self.logs_dir = root / "logs"
        self.backup_dir = root / "backups"
        self.db_patcher = patch.object(db, "DB_FILE", self.db_file)
        self.logs_patcher = patch.object(db, "LOG_DIR", self.logs_dir)
        self.backup_patcher = patch.object(system_setup, "BACKUP_DIR", self.backup_dir)
        self.db_patcher.start()
        self.logs_patcher.start()
        self.backup_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.backup_patcher.stop()
        self.logs_patcher.stop()
        self.db_patcher.stop()
        self.tmp.cleanup()

    def seed_ready_setup(self) -> None:
        now = "2026-05-25T00:00:00Z"
        db.db_execute(
            "INSERT INTO users (username, password_hash, role, enabled, created_at) VALUES (?, ?, 'admin', 1, ?)",
            ("admin", hash_text("not-a-real-password"), now),
        )
        db.db_execute(
            """
            INSERT INTO environments (environment_code, name, enabled, default_workflow_mode, created_at, updated_at)
            VALUES ('DEFAULT', 'Default', 1, 'fast', ?, ?)
            """,
            (now, now),
        )
        db.db_execute(
            """
            INSERT INTO api_keys
            (key_id, name, key_hash, enabled, owner, created_at, allowed_endpoints_json, allowed_environments_json)
            VALUES ('key_test', 'Test key', ?, 1, 'admin', ?, '[]', '[]')
            """,
            (hash_text("caller-plaintext-value"), now),
        )
        db.db_execute(
            """
            INSERT INTO environment_validation_rules
            (environment_code, field_name, label, enabled, required, code_category,
             must_match_code_list, allow_unknown, severity, sort_order, updated_at)
            VALUES ('DEFAULT', 'summary', 'Summary', 1, 1, NULL, 0, 0, 'error', 1, ?)
            """,
            (now,),
        )
        db.db_execute(
            """
            INSERT INTO ai_prompt_versions
            (endpoint, version, name, status, system_prompt, user_template, model, temperature,
             created_at, updated_at, created_by, updated_by)
            VALUES ('cmms-intake', 'v1', 'Default', 'active', 'system', 'user', ?, 0.1, ?, ?, 1, 1)
            """,
            (MODEL_NAME, now, now),
        )
        db.db_execute(
            """
            INSERT INTO ai_output_contracts
            (endpoint, version, name, status, schema_json, strict_mode, created_at, updated_at, created_by, updated_by)
            VALUES ('cmms-intake', 'v1', 'Default', 'active', '{"type":"object"}', 1, ?, ?, 1, 1)
            """,
            (now, now),
        )

    def test_setup_status_reports_ready_checks_without_exposing_secret_values(self) -> None:
        self.seed_ready_setup()

        with patch.dict(os.environ, {"LLM_API_KEY": "env-secret-value"}):
            status = system_setup.build_setup_status(
                ollama_probe=lambda: {"reachable": True, "models": [MODEL_NAME], "error": None}
            )

        items = {item["id"]: item for item in status["items"]}
        self.assertEqual(items["api_running"]["status"], "passed")
        self.assertEqual(items["sqlite_db_initialized"]["status"], "passed")
        self.assertEqual(items["admin_user_exists"]["status"], "passed")
        self.assertEqual(items["llm_api_key_configured"]["status"], "passed")
        self.assertEqual(items["ollama_reachable"]["status"], "passed")
        self.assertEqual(items["qwen_model_available"]["status"], "passed")
        self.assertEqual(items["default_environment_exists"]["status"], "passed")
        self.assertEqual(items["enabled_api_key_exists"]["status"], "passed")
        self.assertEqual(items["required_validation_rule_exists"]["status"], "passed")
        self.assertEqual(items["active_prompt_versions_exist"]["status"], "passed")
        self.assertEqual(items["active_output_contract_exists"]["status"], "passed")
        self.assertEqual(items["logs_directory_writable"]["status"], "passed")
        self.assertEqual(items["backup_directory_writable"]["status"], "passed")
        self.assertNotIn("env-secret-value", json.dumps(status))

    def test_backup_contains_db_and_public_manifest_only(self) -> None:
        self.seed_ready_setup()

        with patch.dict(os.environ, {"LLM_API_KEY": "env-secret-value"}):
            backup = system_setup.create_system_backup(created_by="admin")

        archive_path = Path(backup["file_path"])
        self.assertTrue(archive_path.exists())
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            archive_bytes = b"".join(archive.read(name) for name in archive.namelist())

        self.assertEqual(names, {"manifest.json", "portal.db"})
        self.assertIn(".env", manifest["excluded"])
        self.assertIn("api_keys.json", manifest["excluded"])
        self.assertIn("logs/", manifest["excluded"])
        self.assertNotIn("key_hash", json.dumps(manifest))
        self.assertNotIn("caller-plaintext-value", archive_bytes.decode("latin1"))
        self.assertNotIn("env-secret-value", archive_bytes.decode("latin1"))

    def test_restore_preview_is_non_destructive(self) -> None:
        self.seed_ready_setup()
        backup = system_setup.create_system_backup(created_by="admin")

        preview = system_setup.preview_system_restore(backup_id=backup["backup_id"])

        self.assertEqual(preview["status"], "preview_only")
        self.assertFalse(preview["restore_supported"])
        self.assertEqual(preview["backup_id"], backup["backup_id"])
        self.assertIn("portal.db", preview["contents"])

    def test_normal_users_cannot_access_setup_or_backup_endpoints(self) -> None:
        app = build_management_test_router()
        app.dependency_overrides[current_user] = lambda: PortalUser(user_id=2, username="operator", role="user")
        client = TestClient(app)

        checks = [
            ("GET", "/api/admin/setup/status", None),
            ("POST", "/api/admin/system/backup", None),
            ("GET", "/api/admin/system/backups", None),
            ("POST", "/api/admin/system/restore-preview", {"backup_id": "backup_123"}),
        ]
        for method, path, body in checks:
            with self.subTest(path=path):
                response = client.request(method, path, json=body)
                self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
