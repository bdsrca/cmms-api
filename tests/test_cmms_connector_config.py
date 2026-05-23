import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class CmmsConnectorConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_upsert_returns_masked_secret_status(self) -> None:
        from app.cmms_connectors import public_cmms_connector, upsert_cmms_connector

        connector = upsert_cmms_connector(
            "default",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "auth_header_name": "",
                "secret_value": "super-secret-token",
                "timeout_seconds": 7,
            },
        )

        public = public_cmms_connector(connector)

        self.assertEqual(public["environment_code"], "DEFAULT")
        self.assertTrue(public["enabled"])
        self.assertTrue(public["auto_push_enabled"])
        self.assertEqual(public["auth_type"], "bearer")
        self.assertTrue(public["secret_configured"])
        self.assertNotIn("secret_value", public)
        self.assertNotIn("super-secret-token", str(public))

    def test_update_without_secret_keeps_existing_secret(self) -> None:
        from app.cmms_connectors import build_auth_headers, get_cmms_connector, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": False,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "first-token",
                "timeout_seconds": 5,
            },
        )

        connector = upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": False,
                "auto_push_enabled": False,
                "endpoint_url": "https://cmms.example.test/updated",
                "auth_type": "bearer",
                "timeout_seconds": 9,
            },
        )

        stored = get_cmms_connector("DEFAULT")
        self.assertEqual(connector["endpoint_url"], "https://cmms.example.test/updated")
        self.assertNotEqual(stored["secret_value"], "first-token")
        self.assertNotIn("first-token", str(stored))
        self.assertEqual(build_auth_headers(stored), {"Authorization": "Bearer first-token"})

    def test_custom_header_auth_uses_configured_header_name(self) -> None:
        from app.cmms_connectors import build_auth_headers, upsert_cmms_connector

        connector = upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "header",
                "auth_header_name": "X-CMMS-Key",
                "secret_value": "header-secret",
                "timeout_seconds": 5,
            },
        )

        self.assertEqual(build_auth_headers(connector), {"X-CMMS-Key": "header-secret"})

    def test_extended_settings_are_saved_and_public_without_secret(self) -> None:
        from app.cmms_connectors import public_cmms_connector, upsert_cmms_connector

        connector = upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "extended-secret",
                "http_method": "PUT",
                "success_status_codes": "200,201,204",
                "external_id_path": "data.workOrder.id",
                "dry_run_enabled": True,
                "require_metadata_review": True,
                "static_headers": {"Tenant-ID": "north-campus", "X-Client-ID": "local-api"},
                "payload_root_key": "workOrder",
                "auto_push_note": "Sandbox connector",
            },
        )

        public = public_cmms_connector(connector)

        self.assertEqual(public["http_method"], "PUT")
        self.assertEqual(public["success_status_codes"], "200,201,204")
        self.assertEqual(public["external_id_path"], "data.workOrder.id")
        self.assertTrue(public["dry_run_enabled"])
        self.assertTrue(public["require_metadata_review"])
        self.assertEqual(public["static_headers"], {"Tenant-ID": "north-campus", "X-Client-ID": "local-api"})
        self.assertEqual(public["payload_root_key"], "workOrder")
        self.assertEqual(public["auto_push_note"], "Sandbox connector")
        self.assertNotIn("extended-secret", str(public))

    def test_static_headers_reject_auth_like_names(self) -> None:
        from app.cmms_connectors import upsert_cmms_connector

        with self.assertRaises(ValueError):
            upsert_cmms_connector(
                "DEFAULT",
                {
                    "enabled": True,
                    "auto_push_enabled": True,
                    "endpoint_url": "https://cmms.example.test/work-orders",
                    "auth_type": "bearer",
                    "secret_value": "secret",
                    "static_headers": {"Authorization": "Bearer nope"},
                },
            )


if __name__ == "__main__":
    unittest.main()
