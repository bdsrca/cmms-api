import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import db


def make_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


class ApiKeyScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        os.environ["LLM_API_KEY"] = "scope-env-key"

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_api_keys_schema_has_scope_columns(self) -> None:
        with db.db_connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}

        self.assertIn("allowed_endpoints_json", columns)
        self.assertIn("allowed_environments_json", columns)

    def test_generated_api_key_can_store_list_and_patch_scopes(self) -> None:
        from app.api_keys import create_api_key, list_api_keys, patch_api_key

        user = SimpleNamespace(username="admin")
        created = create_api_key(
            SimpleNamespace(
                name="scoped",
                owner="integration",
                allowed_endpoints=["cmms-intake"],
                allowed_environments=["DEFAULT"],
            ),
            user,
        )

        listed = [row for row in list_api_keys() if row["key_id"] == created["key_id"]][0]
        self.assertEqual(listed["allowed_endpoints"], ["cmms-intake"])
        self.assertEqual(listed["allowed_environments"], ["DEFAULT"])
        self.assertNotIn("api_key", listed)

        patch_api_key(
            created["key_id"],
            SimpleNamespace(
                name=None,
                enabled=None,
                allowed_endpoints=["summarize-work-order", "extract-work-order-fields"],
                allowed_environments=[],
            ),
        )

        updated = [row for row in list_api_keys() if row["key_id"] == created["key_id"]][0]
        self.assertEqual(updated["allowed_endpoints"], ["summarize-work-order", "extract-work-order-fields"])
        self.assertEqual(updated["allowed_environments"], [])

    def test_environment_scopes_are_normalized_to_uppercase(self) -> None:
        from app.api_keys import create_api_key, list_api_keys

        created = create_api_key(
            SimpleNamespace(
                name="lower-env",
                owner=None,
                allowed_endpoints=["cmms-intake"],
                allowed_environments=["default", "Test", "DEFAULT"],
            ),
            SimpleNamespace(username="admin"),
        )

        listed = [row for row in list_api_keys() if row["key_id"] == created["key_id"]][0]
        self.assertEqual(listed["allowed_environments"], ["DEFAULT", "TEST"])

    def test_invalid_endpoint_scope_is_rejected(self) -> None:
        from app.api_keys import create_api_key

        with self.assertRaises(HTTPException) as error:
            create_api_key(
                SimpleNamespace(
                    name="bad-endpoint",
                    owner=None,
                    allowed_endpoints=["cmms-intake", "not-a-real-endpoint"],
                    allowed_environments=[],
                ),
                SimpleNamespace(username="admin"),
            )

        self.assertEqual(error.exception.status_code, 422)

    def test_generated_api_key_scope_blocks_disallowed_endpoint_and_environment(self) -> None:
        from app.api_keys import create_api_key, enforce_api_key_scope, require_api_key

        created = create_api_key(
            SimpleNamespace(
                name="intake-default-only",
                owner=None,
                allowed_endpoints=["cmms-intake"],
                allowed_environments=["DEFAULT"],
            ),
            SimpleNamespace(username="admin"),
        )
        request = make_request()
        require_api_key(request, created["api_key"])

        enforce_api_key_scope(request, "cmms-intake", "DEFAULT")

        with self.assertRaises(HTTPException) as endpoint_error:
            enforce_api_key_scope(request, "summarize-work-order", "DEFAULT")
        self.assertEqual(endpoint_error.exception.status_code, 403)
        self.assertIn("endpoint", endpoint_error.exception.detail.lower())

        with self.assertRaises(HTTPException) as environment_error:
            enforce_api_key_scope(request, "cmms-intake", "TEST")
        self.assertEqual(environment_error.exception.status_code, 403)
        self.assertIn("environment", environment_error.exception.detail.lower())

    def test_env_llm_api_key_remains_unrestricted_for_ai_endpoints(self) -> None:
        from app.api_keys import enforce_api_key_scope, require_api_key

        request = make_request()
        require_api_key(request, "scope-env-key")

        enforce_api_key_scope(request, "summarize-work-order", "ANY")
        enforce_api_key_scope(request, "cmms-intake", "DEFAULT")

    def test_ai_route_rejects_generated_key_for_disallowed_endpoint(self) -> None:
        from app.ai_routes import build_ai_router
        from app.api_keys import create_api_key
        from app.models import (
            AssistantResponse,
            EmailIntakeRequest,
            ExtractFieldsRequest,
            ExtractFieldsResponse,
            IntakeResponse,
            SummaryResponse,
            TextRequest,
        )

        calls = []

        async def fake_call_ollama(*args, **kwargs):
            calls.append((args, kwargs))
            return "should not be called"

        app = FastAPI()
        app.include_router(
            build_ai_router(
                call_ollama=fake_call_ollama,
                text_request_model=TextRequest,
                summary_response_model=SummaryResponse,
                assistant_response_model=AssistantResponse,
                extract_fields_request_model=ExtractFieldsRequest,
                extract_fields_response_model=ExtractFieldsResponse,
                email_intake_request_model=EmailIntakeRequest,
                intake_response_model=IntakeResponse,
            )
        )
        created = create_api_key(
            SimpleNamespace(
                name="intake-only",
                owner=None,
                allowed_endpoints=["cmms-intake"],
                allowed_environments=[],
            ),
            SimpleNamespace(username="admin"),
        )

        response = TestClient(app).post(
            "/api/ai/summarize-work-order",
            headers={"x-api-key": created["api_key"]},
            json={"text": "Broken light in ARC 205."},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(calls, [])

    def test_ai_route_rejects_generated_key_for_disallowed_environment(self) -> None:
        from app.ai_routes import build_ai_router
        from app.api_keys import create_api_key
        from app.models import (
            AssistantResponse,
            EmailIntakeRequest,
            ExtractFieldsRequest,
            ExtractFieldsResponse,
            IntakeResponse,
            SummaryResponse,
            TextRequest,
        )

        calls = []

        async def fake_call_ollama(*args, **kwargs):
            calls.append((args, kwargs))
            return "should not be called"

        app = FastAPI()
        app.include_router(
            build_ai_router(
                call_ollama=fake_call_ollama,
                text_request_model=TextRequest,
                summary_response_model=SummaryResponse,
                assistant_response_model=AssistantResponse,
                extract_fields_request_model=ExtractFieldsRequest,
                extract_fields_response_model=ExtractFieldsResponse,
                email_intake_request_model=EmailIntakeRequest,
                intake_response_model=IntakeResponse,
            )
        )
        created = create_api_key(
            SimpleNamespace(
                name="default-only",
                owner=None,
                allowed_endpoints=["summarize-work-order"],
                allowed_environments=["DEFAULT"],
            ),
            SimpleNamespace(username="admin"),
        )

        response = TestClient(app).post(
            "/api/ai/summarize-work-order",
            headers={"x-api-key": created["api_key"]},
            json={"text": "Broken light in ARC 205.", "environment_code": "TEST"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(calls, [])

    def test_api_key_ui_exposes_scope_fields(self) -> None:
        html = Path("app/ui.py").read_text(encoding="utf-8")

        self.assertIn("kAllowedEndpoints", html)
        self.assertIn("kAllowedEnvironments", html)
        self.assertIn("allowed_endpoints", html)
        self.assertIn("allowed_environments", html)


if __name__ == "__main__":
    unittest.main()
