import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.security import PortalUser, current_admin, current_user


class CmmsConnectorMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def client(self, role: str = "admin") -> TestClient:
        from app.cmms_connector_routes import router

        app = FastAPI()
        app.include_router(router)
        if role == "admin":
            app.dependency_overrides[current_admin] = lambda: PortalUser(user_id=1, username="admin", role="admin")
        else:
            app.dependency_overrides[current_user] = lambda: PortalUser(user_id=2, username="operator", role=role)
        return TestClient(app)

    def save_connector(self) -> None:
        from app.cmms_connectors import upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": False,
                "dry_run_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "route-secret",
                "payload_root_key": "workOrder",
                "field_mappings": [
                    {"source": "summary", "target": "description", "required": True},
                    {"source": "priority", "target": "priorityCode", "required": True},
                    {"source": "asset_context.asset_id", "target": "asset.id"},
                ],
            },
        )

    def test_connector_stores_public_field_mappings_without_secret(self) -> None:
        from app.cmms_connectors import get_cmms_connector, public_cmms_connector

        self.save_connector()

        public = public_cmms_connector(get_cmms_connector("DEFAULT"))

        self.assertEqual(public["field_mappings"][0]["source"], "summary")
        self.assertEqual(public["field_mappings"][0]["target"], "description")
        self.assertTrue(public["field_mappings"][0]["required"])
        self.assertTrue(public["secret_configured"])
        self.assertNotIn("route-secret", str(public))

    def test_dry_run_maps_canonical_payload_without_network_sender(self) -> None:
        from app.cmms_connectors import dry_run_cmms_connector_mapping

        self.save_connector()
        canonical = {
            "summary": "Leaking pipe",
            "priority": "High",
            "asset_context": {"asset_id": "AHU-3"},
            "building": "North",
        }

        result = dry_run_cmms_connector_mapping("DEFAULT", canonical)

        self.assertEqual(result["status"], "preview")
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["mapped_payload"]["description"], "Leaking pipe")
        self.assertEqual(result["mapped_payload"]["priorityCode"], "High")
        self.assertEqual(result["mapped_payload"]["asset"]["id"], "AHU-3")
        self.assertEqual(result["outgoing_payload"]["workOrder"]["description"], "Leaking pipe")
        self.assertIn("building", result["unmapped_fields"])
        self.assertEqual(result["missing_required_fields"], [])

    def test_dry_run_reports_missing_required_fields(self) -> None:
        from app.cmms_connectors import dry_run_cmms_connector_mapping

        self.save_connector()

        result = dry_run_cmms_connector_mapping("DEFAULT", {"summary": "Leaking pipe"})

        self.assertEqual(result["status"], "preview")
        self.assertIn("priority", result["missing_required_fields"])
        priority = next(item for item in result["mapping_results"] if item["source"] == "priority")
        self.assertEqual(priority["status"], "missing_required")

    def test_manual_probe_keeps_fixed_probe_payload_when_mappings_exist(self) -> None:
        from app.cmms_connectors import probe_cmms_connector

        self.save_connector()
        calls = []

        result = probe_cmms_connector(
            "DEFAULT",
            sender=lambda **kwargs: calls.append(kwargs) or {"status_code": 200, "json": {"id": "PROBE-1"}},
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(calls[0]["json_payload"]["workOrder"]["schema"], "cmms_connector_probe_v1")
        self.assertTrue(calls[0]["json_payload"]["workOrder"]["dry_run"])

    def test_route_dry_run_preview_does_not_require_live_push(self) -> None:
        self.save_connector()
        client = self.client()

        response = client.post(
            "/api/admin/environments/DEFAULT/cmms-connector/dry-run",
            json={"canonical_payload": {"summary": "Leak", "priority": "High"}},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "preview")
        self.assertTrue(data["dry_run"])
        self.assertEqual(data["outgoing_payload"]["workOrder"]["description"], "Leak")

    def test_normal_users_cannot_dry_run_connector_mapping(self) -> None:
        client = self.client(role="user")

        response = client.post(
            "/api/admin/environments/DEFAULT/cmms-connector/dry-run",
            json={"canonical_payload": {"summary": "Leak"}},
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
