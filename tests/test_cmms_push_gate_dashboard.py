import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class CmmsPushGateDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def insert_push_step(self, run_id: str, status: str, blocked_reasons: list[str] | None = None) -> None:
        db.db_execute(
            """
            INSERT INTO workflow_runs
            (run_id, endpoint, environment_code, source, status, started_at)
            VALUES (?, 'cmms-intake', 'DEFAULT', 'test', 'completed', '2026-05-24T00:00:00Z')
            """,
            (run_id,),
        )
        db.db_execute(
            """
            INSERT INTO workflow_run_steps
            (run_id, step_name, step_order, status, started_at, output_summary, output_json)
            VALUES (?, 'cmms_auto_push', 48, 'passed', '2026-05-24T00:00:01Z', ?, ?)
            """,
            (
                run_id,
                f"cmms_push={status}",
                json.dumps(
                    {
                        "status": status,
                        "environment_code": "DEFAULT",
                        "blocked_reasons": blocked_reasons or [],
                    }
                ),
            ),
        )

    def test_dashboard_includes_cmms_push_gate_summary(self) -> None:
        from app.regression_dashboard import build_regression_dashboard

        self.insert_push_step("run-ready", "dry_run")
        self.insert_push_step("run-sent", "sent")
        self.insert_push_step("run-blocked", "blocked", ["review_not_passed", "handoff_not_ready"])

        dashboard = build_regression_dashboard()
        summary = dashboard["cmms_push_gate_summary"]

        self.assertEqual(summary["ready_count"], 2)
        self.assertEqual(summary["sent_count"], 1)
        self.assertEqual(summary["dry_run_count"], 1)
        self.assertEqual(summary["blocked_count"], 1)
        self.assertEqual(summary["top_blocked_reasons"][0], {"reason": "review_not_passed", "count": 1})
        self.assertEqual(summary["recent_ready_runs"][0]["run_id"], "run-sent")
        self.assertEqual(summary["recent_blocked_runs"][0]["run_id"], "run-blocked")


if __name__ == "__main__":
    unittest.main()
