import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class CmmsAutoPushTests(unittest.TestCase):
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
            "contract_valid": True,
            "ai_validation_valid": True,
            "can_create_work_order": True,
            "human_review_required": False,
            "review_passed": True,
            "handoff_status": "ready",
        }

    def save_ready_connector(self, endpoint: str = "https://cmms.example.test/work-orders") -> None:
        from app.cmms_connectors import upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": endpoint,
                "auth_type": "bearer",
                "secret_value": "push-token",
                "timeout_seconds": 3,
            },
        )

    def test_auto_push_skips_without_connector_config(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload

        calls = []
        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=lambda **kwargs: calls.append(kwargs))

        self.assertEqual(result["status"], "skipped")
        self.assertIn("connector_not_configured", result["blocked_reasons"])
        self.assertEqual(calls, [])

    def test_auto_push_blocks_when_human_review_required(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload

        self.save_ready_connector()
        context = self.ready_context()
        context["human_review_required"] = True
        calls = []

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, context, sender=lambda **kwargs: calls.append(kwargs))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("human_review_required", result["blocked_reasons"])
        self.assertEqual(calls, [])

    def test_auto_push_blocks_when_safety_review_did_not_pass(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload

        self.save_ready_connector()
        context = self.ready_context()
        context["review_passed"] = False

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, context, sender=lambda **kwargs: None)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("review_not_passed", result["blocked_reasons"])

    def test_auto_push_blocks_non_https_non_local_endpoint(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload

        self.save_ready_connector(endpoint="http://cmms.example.test/work-orders")

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=lambda **kwargs: None)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("endpoint_must_be_https_or_localhost", result["blocked_reasons"])

    def test_auto_push_sends_once_when_all_gates_pass(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload

        self.save_ready_connector()
        calls = []

        def fake_sender(**kwargs):
            calls.append(kwargs)
            return {"status_code": 201, "json": {"id": "WO-123", "message": "Created"}}

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=fake_sender)

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["status_code"], 201)
        self.assertEqual(result["external_reference"], "WO-123")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer push-token")
        self.assertEqual(calls[0]["json_payload"], {"summary": "Leak"})

    def test_failed_response_is_sanitized(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload

        self.save_ready_connector()

        def fake_sender(**kwargs):
            return {"status_code": 500, "text": "Authorization: Bearer push-token failed hard"}

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=fake_sender)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["status_code"], 500)
        self.assertNotIn("push-token", result["message"])

    def test_dry_run_does_not_call_sender(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "dry_run_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "push-token",
            },
        )
        calls = []

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=lambda **kwargs: calls.append(kwargs))

        self.assertEqual(result["status"], "dry_run")
        self.assertTrue(result["dry_run_enabled"])
        self.assertEqual(calls, [])

    def test_method_static_headers_payload_wrapper_success_codes_and_external_path_are_used(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders/WO-123",
                "auth_type": "bearer",
                "secret_value": "push-token",
                "http_method": "PUT",
                "success_status_codes": "204",
                "external_id_path": "data.workOrder.id",
                "static_headers": {"Tenant-ID": "north-campus"},
                "payload_root_key": "workOrder",
                "timeout_seconds": 6,
            },
        )
        calls = []

        def fake_sender(**kwargs):
            calls.append(kwargs)
            return {"status_code": 204, "json": {"data": {"workOrder": {"id": "WO-999"}}}}

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=fake_sender)

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["external_reference"], "WO-999")
        self.assertEqual(calls[0]["http_method"], "PUT")
        self.assertEqual(calls[0]["headers"]["Tenant-ID"], "north-campus")
        self.assertEqual(calls[0]["json_payload"], {"workOrder": {"summary": "Leak"}})
        self.assertEqual(calls[0]["timeout_seconds"], 6)

    def test_require_metadata_review_blocks_until_context_confirms_review(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "require_metadata_review": True,
                "endpoint_url": "https://cmms.example.test/work-orders",
                "auth_type": "bearer",
                "secret_value": "push-token",
            },
        )

        blocked = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context(), sender=lambda **kwargs: None)
        reviewed_context = self.ready_context()
        reviewed_context["metadata_reviewed"] = True
        sent = auto_push_cmms_payload(
            "DEFAULT",
            {"summary": "Leak"},
            reviewed_context,
            sender=lambda **kwargs: {"status_code": 201, "json": {"id": "WO-321"}},
        )

        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("metadata_review_required", blocked["blocked_reasons"])
        self.assertEqual(sent["status"], "sent")

    def test_probe_requires_dry_run_enabled(self) -> None:
        from app.cmms_connectors import probe_cmms_connector

        self.save_ready_connector()
        calls = []

        result = probe_cmms_connector("DEFAULT", sender=lambda **kwargs: calls.append(kwargs))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("dry_run_required_for_probe", result["blocked_reasons"])
        self.assertEqual(calls, [])

    def test_probe_sends_fixed_payload_when_dry_run_enabled(self) -> None:
        from app.cmms_connectors import probe_cmms_connector, upsert_cmms_connector

        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": False,
                "dry_run_enabled": True,
                "endpoint_url": "https://cmms.example.test/work-orders/probe",
                "auth_type": "bearer",
                "secret_value": "push-token",
                "http_method": "PATCH",
                "success_status_codes": "200",
                "external_id_path": "probe.id",
                "static_headers": {"Tenant-ID": "north-campus"},
                "payload_root_key": "workOrder",
            },
        )
        calls = []

        def fake_sender(**kwargs):
            calls.append(kwargs)
            return {"status_code": 200, "json": {"probe": {"id": "PROBE-1"}, "message": "ok"}}

        result = probe_cmms_connector("DEFAULT", sender=fake_sender)

        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["probe"])
        self.assertEqual(result["external_reference"], "PROBE-1")
        self.assertEqual(calls[0]["http_method"], "PATCH")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer push-token")
        self.assertEqual(calls[0]["headers"]["Tenant-ID"], "north-campus")
        self.assertEqual(calls[0]["json_payload"]["workOrder"]["schema"], "cmms_connector_probe_v1")
        self.assertTrue(calls[0]["json_payload"]["workOrder"]["dry_run"])


if __name__ == "__main__":
    unittest.main()
