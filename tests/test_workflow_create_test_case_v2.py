import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import db
from app.security import PortalUser


class WorkflowCreateTestCaseV2Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    async def test_create_test_case_from_run_uses_clean_expected_template(self) -> None:
        from app.test_cases import create_test_case_from_workflow_run

        actual = {
            "result": {
                "summary": "Water leak in ARC room 205 needs urgent plumbing review.",
                "building": "ARC",
                "room": "205",
                "priority": "URGENT",
                "work_order_type": "PLUMB",
            },
            "contract": {"valid": True},
            "ai_validation": {
                "valid": False,
                "errors": [{"field": "priority", "message": "Priority is not configured."}],
                "warnings": [{"field": "room", "message": "Room is not configured."}],
            },
        }
        db.db_execute(
            """
            INSERT INTO ai_test_cases
            (name, endpoint, environment_code, input_text, source, expected_json, enabled, created_at, updated_at)
            VALUES ('Original', 'cmms-intake', 'DEFAULT', 'ARC 205 has an urgent leak.', 'manual', '{}', 1, 'now', 'now')
            """
        )
        db.db_execute(
            """
            INSERT INTO ai_test_case_runs
            (test_case_id, run_id, endpoint, environment_code, status, started_at, actual_json, comparison_json)
            VALUES (1, 'run-template-1', 'cmms-intake', 'DEFAULT', 'failed', 'now', ?, '{}')
            """,
            (json.dumps(actual),),
        )

        created = await create_test_case_from_workflow_run(
            "run-template-1",
            SimpleNamespace(name="Regression from run", expected_json=None, tags="trace", notes="from run"),
            PortalUser(user_id=1, username="admin", role="admin"),
        )
        row = db.db_fetchone("SELECT * FROM ai_test_cases WHERE id = ?", (created["test_case_id"],))
        expected = json.loads(row["expected_json"])

        self.assertEqual(expected["summary_contains"], ["Water leak in ARC room 205 needs urgent"])
        self.assertEqual(expected["building"], "ARC")
        self.assertEqual(expected["room"], "205")
        self.assertEqual(expected["priority"], "URGENT")
        self.assertEqual(expected["work_order_type"], "PLUMB")
        self.assertTrue(expected["contract_valid"])
        self.assertFalse(expected["environment_valid"])
        self.assertEqual(expected["expected_errors"], ["priority"])
        self.assertEqual(expected["expected_warnings"], ["room"])
        self.assertNotIn("drafts", expected)
        self.assertNotIn("raw", expected)


if __name__ == "__main__":
    unittest.main()
