import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.security import PortalUser, current_admin


class DemoEnvironmentSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_seed_demo_environment_adds_assets_shifts_technicians_and_fake_connector(self) -> None:
        from app.asset_registry import resolve_asset_context
        from app.cmms_connectors import get_cmms_connector, public_cmms_connector
        from app.demo_environment import seed_demo_environment
        from app.environments import list_codes
        from app.technician_roster import resolve_assignment_context

        result = seed_demo_environment("DEFAULT")

        self.assertEqual(result["environment_code"], "DEFAULT")
        self.assertGreaterEqual(result["counts"]["assets"], 5)
        self.assertGreaterEqual(result["counts"]["technician_roster"], 5)
        self.assertIn("night", result["shifts"])
        self.assertIn("day", result["shifts"])
        self.assertIn("evening", result["shifts"])

        rows = list_codes("DEFAULT")["rows"]
        categories = {row["category"] for row in rows}
        self.assertIn("assets", categories)
        self.assertIn("technician_roster", categories)
        self.assertIn("assign_to", categories)
        self.assertIn("issue_to_employee_number", categories)
        self.assertIn("job_type", categories)

        asset_context = resolve_asset_context("Create urgent AHU-3 filter work order.", "DEFAULT")
        self.assertEqual(asset_context["status"], "resolved")
        self.assertEqual(asset_context["asset"]["code"], "AHU-3")
        self.assertEqual(asset_context["planning_hints"]["work_order_type"], "HVAC")
        self.assertEqual(
            asset_context["planning_hints"]["likely_parts"][0]["part_number"],
            "FILTER-AHU-20X25X2",
        )

        assignment_context = resolve_assignment_context(
            "Assign the AHU-3 work order to tonight's on-duty technician.",
            "DEFAULT",
            trade="HVAC",
        )
        self.assertEqual(assignment_context["status"], "resolved")
        self.assertEqual(assignment_context["assignment"]["assign_to"], "Nina Night")
        self.assertEqual(assignment_context["assignment"]["issue_to"], "100")

        connector = public_cmms_connector(get_cmms_connector("DEFAULT"))
        self.assertTrue(connector["configured"])
        self.assertTrue(connector["enabled"])
        self.assertTrue(connector["auto_push_enabled"])
        self.assertTrue(connector["dry_run_enabled"])
        self.assertTrue(connector["secret_configured"])
        self.assertEqual(connector["endpoint_url"], "http://localhost/fake-cmms/work-orders")
        self.assertNotIn("secret_value", connector)

    def test_admin_route_seeds_demo_environment(self) -> None:
        from app.environment_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_admin] = lambda: PortalUser(user_id=1, username="admin", role="admin")
        client = TestClient(app)

        response = client.post("/api/admin/environments/default/demo-setup")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["environment_code"], "DEFAULT")
        self.assertGreaterEqual(body["counts"]["assets"], 5)
        self.assertGreaterEqual(body["counts"]["technician_roster"], 5)
        self.assertTrue(body["connector"]["dry_run_enabled"])
        self.assertTrue(body["connector"]["auto_push_enabled"])

    def test_environment_ui_exposes_demo_setup_action(self) -> None:
        source = Path("app/ui.py").read_text(encoding="utf-8")

        self.assertIn("seedDemoEnvironment", source)
        self.assertIn("/demo-setup", source)
        self.assertIn("Load demo setup", source)


if __name__ == "__main__":
    unittest.main()
