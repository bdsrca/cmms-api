import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class CmmsPushAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def ready_context(self) -> dict:
        return {
            "run_id": "run-audit-1",
            "contract_valid": True,
            "ai_validation_valid": True,
            "can_create_work_order": True,
            "human_review_required": False,
            "review_passed": True,
            "handoff_status": "ready",
        }

    def test_sent_push_records_sanitized_audit_event(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload, list_cmms_push_events, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "audit-token",
            },
        )

        result = auto_push_cmms_payload(
            "DEFAULT",
            {"summary": "Leak", "internal_note": "do not persist full payload"},
            self.ready_context(),
            sender=lambda **kwargs: {
                "status_code": 201,
                "json": {"id": "WO-AUDIT-1", "message": "created with audit-token"},
            },
        )
        events = list_cmms_push_events("DEFAULT")

        self.assertEqual(result["status"], "sent")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["run_id"], "run-audit-1")
        self.assertEqual(event["environment_code"], "DEFAULT")
        self.assertEqual(event["status"], "sent")
        self.assertEqual(event["status_code"], 201)
        self.assertEqual(event["external_reference"], "WO-AUDIT-1")
        self.assertEqual(event["blocked_reasons"], [])
        self.assertNotIn("audit-token", str(event))
        self.assertNotIn("do not persist full payload", str(event))

    def test_blocked_push_records_audit_event_without_payload(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload, list_cmms_push_events, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "audit-token",
            },
        )
        context = self.ready_context()
        context["review_passed"] = False

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, context, sender=lambda **kwargs: None)
        events = list_cmms_push_events("DEFAULT")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], "blocked")
        self.assertEqual(events[0]["blocked_reasons"], ["review_not_passed"])
        self.assertIsNone(events[0]["status_code"])


if __name__ == "__main__":
    unittest.main()
