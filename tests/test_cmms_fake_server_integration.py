import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from app import db


class _FakeCmmsHandler(BaseHTTPRequestHandler):
    received: dict = {}

    def do_PUT(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.__class__.received = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "tenant": self.headers.get("Tenant-ID"),
            "body": json.loads(body),
        }
        response = json.dumps({"data": {"workOrder": {"id": "WO-LOCAL-1"}}, "message": "created"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args) -> None:
        return


class CmmsFakeServerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        _FakeCmmsHandler.received = {}
        self.server = HTTPServer(("127.0.0.1", 0), _FakeCmmsHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.db_patcher.stop()
        self.tmp.cleanup()

    def ready_context(self) -> dict:
        return {
            "run_id": "run-local-1",
            "contract_valid": True,
            "ai_validation_valid": True,
            "can_create_work_order": True,
            "human_review_required": False,
            "review_passed": True,
            "handoff_status": "ready",
        }

    def test_default_sender_posts_to_local_fake_cmms(self) -> None:
        from app.cmms_connectors import auto_push_cmms_payload, upsert_cmms_connector

        endpoint = f"http://127.0.0.1:{self.server.server_port}/work-orders/WO-LOCAL-1"
        upsert_cmms_connector(
            "DEFAULT",
            {
                "enabled": True,
                "auto_push_enabled": True,
                "endpoint_url": endpoint,
                "auth_type": "bearer",
                "secret_value": "local-token",
                "http_method": "PUT",
                "success_status_codes": "200",
                "external_id_path": "data.workOrder.id",
                "static_headers": {"Tenant-ID": "north-campus"},
                "payload_root_key": "workOrder",
            },
        )

        result = auto_push_cmms_payload("DEFAULT", {"summary": "Leak"}, self.ready_context())

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["external_reference"], "WO-LOCAL-1")
        self.assertEqual(_FakeCmmsHandler.received["path"], "/work-orders/WO-LOCAL-1")
        self.assertEqual(_FakeCmmsHandler.received["authorization"], "Bearer local-token")
        self.assertEqual(_FakeCmmsHandler.received["tenant"], "north-campus")
        self.assertEqual(_FakeCmmsHandler.received["body"], {"workOrder": {"summary": "Leak"}})


if __name__ == "__main__":
    unittest.main()
