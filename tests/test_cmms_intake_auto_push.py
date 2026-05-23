import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.environments import seed_default_environment


class CmmsIntakeAutoPushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()
        db.db_execute(
            """
            INSERT INTO code_values
            (environment_code, category, code, label, aliases, metadata_json, source, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, NULL, 'Manual', 1, ?, ?)
            """,
            ("DEFAULT", "issue_to", "0000", "0000", db.now_text(), db.now_text()),
        )

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def save_ready_connector(self) -> None:
        from app.cmms_connectors import upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "intake-token",
                "timeout_seconds": 3,
            },
        )

    def ready_result(self) -> dict:
        return {
            "summary": "Water leak under sink",
            "building": "ARC",
            "room": "205",
            "priority": "URGENT",
            "work_order_type": "Plumbing",
            "assign_to": "Facilities",
            "issue_to": "0000",
            "job_type": "Maintenance",
        }

    def test_intake_auto_push_sends_when_gates_pass(self) -> None:
        from app.ai_endpoints import build_cmms_intake_push_result

        self.save_ready_connector()
        calls = []

        def fake_sender(**kwargs):
            calls.append(kwargs)
            return {"status_code": 201, "json": {"id": "WO-456"}}

        result = build_cmms_intake_push_result(
            run_id="run-1",
            environment_code="DEFAULT",
            payload=self.ready_result(),
            contract_valid=True,
            ai_validation={"valid": True},
            validation={"can_create_work_order": True, "needs_human_review": False},
            review={"status": "pass", "human_review_recommended": False},
            metadata_review={"reviewed": True},
            sender=fake_sender,
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["external_reference"], "WO-456")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["json_payload"]["schema"], "canonical_cmms_work_order_v1")

    def test_intake_auto_push_blocks_when_reviewer_recommends_human_review(self) -> None:
        from app.ai_endpoints import build_cmms_intake_push_result

        self.save_ready_connector()
        calls = []

        result = build_cmms_intake_push_result(
            run_id="run-1",
            environment_code="DEFAULT",
            payload=self.ready_result(),
            contract_valid=True,
            ai_validation={"valid": True},
            validation={"can_create_work_order": True, "needs_human_review": False},
            review={"status": "warning", "human_review_recommended": True},
            metadata_review={"reviewed": True},
            sender=lambda **kwargs: calls.append(kwargs),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("human_review_required", result["blocked_reasons"])
        self.assertEqual(calls, [])

    def test_intake_auto_push_blocks_when_review_status_is_not_pass(self) -> None:
        from app.ai_endpoints import build_cmms_intake_push_result

        self.save_ready_connector()

        result = build_cmms_intake_push_result(
            run_id="run-1",
            environment_code="DEFAULT",
            payload=self.ready_result(),
            contract_valid=True,
            ai_validation={"valid": True},
            validation={"can_create_work_order": True, "needs_human_review": False},
            review={"status": "warning", "human_review_recommended": False},
            metadata_review={"reviewed": True},
            sender=lambda **kwargs: None,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("review_not_passed", result["blocked_reasons"])


if __name__ == "__main__":
    unittest.main()
