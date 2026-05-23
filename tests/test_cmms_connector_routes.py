import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.security import PortalUser, current_admin


class CmmsConnectorRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def client(self) -> TestClient:
        from app.cmms_connector_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_admin] = lambda: PortalUser(user_id=1, username="admin", role="admin")
        return TestClient(app)

    def test_put_and_get_connector_masks_secret(self) -> None:
        client = self.client()

        saved = client.put(
            "/api/admin/environments/default/cmms-connector",
            json={
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "header",
                "auth_header_name": "X-CMMS-Key",
                "secret_value": "route-secret",
                "timeout_seconds": 4,
                "http_method": "PATCH",
                "success_status_codes": "200,202,204",
                "external_id_path": "result.id",
                "dry_run_enabled": True,
                "require_metadata_review": True,
                "static_headers": {"Tenant-ID": "north-campus"},
                "payload_root_key": "workOrder",
                "auto_push_note": "Route test",
            },
        )
        fetched = client.get("/api/admin/environments/DEFAULT/cmms-connector")

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(fetched.status_code, 200)
        self.assertTrue(fetched.json()["secret_configured"])
        self.assertEqual(fetched.json()["auth_type"], "header")
        self.assertEqual(fetched.json()["http_method"], "PATCH")
        self.assertEqual(fetched.json()["success_status_codes"], "200,202,204")
        self.assertEqual(fetched.json()["external_id_path"], "result.id")
        self.assertTrue(fetched.json()["dry_run_enabled"])
        self.assertTrue(fetched.json()["require_metadata_review"])
        self.assertEqual(fetched.json()["static_headers"], {"Tenant-ID": "north-campus"})
        self.assertEqual(fetched.json()["payload_root_key"], "workOrder")
        self.assertEqual(fetched.json()["auto_push_note"], "Route test")
        self.assertNotIn("secret_value", fetched.json())
        self.assertNotIn("route-secret", str(fetched.json()))

    def test_get_missing_connector_returns_unconfigured_shape(self) -> None:
        response = self.client().get("/api/admin/environments/DEFAULT/cmms-connector")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"configured": False, "secret_configured": False})

    def test_test_endpoint_reports_config_validation(self) -> None:
        client = self.client()
        client.put(
            "/api/admin/environments/DEFAULT/cmms-connector",
            json={
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "http://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "route-secret",
            },
        )

        response = client.post("/api/admin/environments/DEFAULT/cmms-connector/test")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "blocked")
        self.assertIn("endpoint_must_be_https_or_localhost", response.json()["blocked_reasons"])

    def test_put_invalid_connector_settings_returns_400(self) -> None:
        response = self.client().put(
            "/api/admin/environments/DEFAULT/cmms-connector",
            json={
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "route-secret",
                "static_headers": {"Authorization": "Bearer static-secret"},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("static_headers", response.json()["detail"])

    def test_get_push_events_returns_recent_environment_audit(self) -> None:
        from app.cmms_connectors import record_cmms_push_event

        record_cmms_push_event(
            "DEFAULT",
            {"run_id": "run-route-audit"},
            {
                "status": "blocked",
                "blocked_reasons": ["review_not_passed"],
                "connector_enabled": True,
                "auto_push_enabled": True,
            },
        )

        response = self.client().get("/api/admin/environments/DEFAULT/cmms-connector/push-events")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["run_id"], "run-route-audit")
        self.assertEqual(response.json()[0]["blocked_reasons"], ["review_not_passed"])

    def test_probe_endpoint_returns_probe_result(self) -> None:
        with patch("app.cmms_connector_routes.probe_cmms_connector") as probe:
            probe.return_value = {"status": "sent", "probe": True, "status_code": 200}

            response = self.client().post("/api/admin/environments/DEFAULT/cmms-connector/probe")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sent")
        self.assertTrue(response.json()["probe"])
        probe.assert_called_once_with("DEFAULT")


if __name__ == "__main__":
    unittest.main()
