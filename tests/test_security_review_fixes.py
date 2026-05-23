import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.security import PortalUser, current_admin, current_user


class SecurityReviewFixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_default_api_key_route_does_not_return_llm_api_key(self) -> None:
        from app.core_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_user] = lambda: PortalUser(user_id=1, username="user", role="user")

        with patch.dict(os.environ, {"LLM_API_KEY": "super-secret-local-key"}, clear=False):
            response = TestClient(app).get("/api/default-api-key")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("super-secret-local-key", str(response.json()))
        self.assertEqual(response.json()["api_key"], "")

    def test_portal_ui_does_not_hardcode_or_fetch_default_api_key(self) -> None:
        html = Path("app/ui.py").read_text(encoding="utf-8")

        self.assertNotIn('defaultApiKey: "my-secret-key"', html)
        self.assertNotIn('/api/default-api-key', html)

    def test_cmms_connector_secret_is_not_stored_plaintext_but_still_usable(self) -> None:
        from app.cmms_connectors import build_auth_headers, get_cmms_connector, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "plain-token",
            },
        )

        stored = get_cmms_connector("DEFAULT")

        self.assertIsNotNone(stored)
        self.assertNotEqual(stored["secret_value"], "plain-token")
        self.assertNotIn("plain-token", str(stored))
        self.assertEqual(build_auth_headers(stored), {"Authorization": "Bearer plain-token"})

    def test_plaintext_connector_secret_migration_protects_existing_rows(self) -> None:
        from app.cmms_connectors import build_auth_headers, get_cmms_connector, migrate_plaintext_connector_secrets
        from app.db import db_execute

        db_execute(
            """
            INSERT INTO cmms_connectors (
                environment_code, enabled, auto_push_enabled, endpoint_url, auth_type,
                secret_value, created_at, updated_at
            )
            VALUES ('DEFAULT', 1, 1, 'https://cmms.example.test/work-orders', 'bearer', 'legacy-token', 'now', 'now')
            """
        )

        migrate_plaintext_connector_secrets()
        stored = get_cmms_connector("DEFAULT")

        self.assertNotEqual(stored["secret_value"], "legacy-token")
        self.assertNotIn("legacy-token", str(stored))
        self.assertEqual(build_auth_headers(stored), {"Authorization": "Bearer legacy-token"})

    def test_system_status_requires_local_api_key_and_admin_session(self) -> None:
        from app.management_routes import build_management_router
        from app.main import require_local_control

        async def is_ollama_running() -> bool:
            return False

        async def wait_for_ollama() -> bool:
            return False

        app = FastAPI()
        app.include_router(
            build_management_router(
                require_local_control=require_local_control,
                is_ollama_running=is_ollama_running,
                wait_for_ollama=wait_for_ollama,
                start_ollama_process=lambda: None,
                stop_ollama_process=lambda: None,
                shutdown_process_later=lambda: None,
            )
        )
        app.dependency_overrides[current_admin] = lambda: PortalUser(user_id=1, username="admin", role="admin")

        with patch.dict(os.environ, {"LOCAL_CONTROL_API_KEY": "local-control-key"}, clear=False):
            client = TestClient(app)
            missing = client.get("/api/system/status")
            allowed = client.get("/api/system/status", headers={"x-api-key": "local-control-key"})

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(allowed.status_code, 200)


if __name__ == "__main__":
    unittest.main()
