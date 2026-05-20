from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analytics_router import summarize_events
from contract_validator import validate_contract
from environment_validator import validate_environment
from free_token_policy import issue_free_token, revoke_token, verify_token
from intake_pipeline import run_text_intake
from secure_logger import build_event, redact_payload


class ShowcaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = json.loads((ROOT / "data" / "sample_environment.json").read_text())

    def test_free_token_allows_scoped_intake(self) -> None:
        raw, token = issue_free_token(environment_code="DEMO", scopes=["intake:text"])
        ok, reason = verify_token(raw, token, scope="intake:text", environment_code="DEMO")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_free_token_rejects_wrong_scope(self) -> None:
        raw, token = issue_free_token(environment_code="DEMO", scopes=["intake:text"])
        ok, reason = verify_token(raw, token, scope="tokens:manage", environment_code="DEMO")
        self.assertFalse(ok)
        self.assertEqual(reason, "scope_not_allowed")

    def test_free_token_can_be_revoked(self) -> None:
        raw, token = issue_free_token(environment_code="DEMO", scopes=["intake:text"])
        revoke_token(token)
        ok, reason = verify_token(raw, token, scope="intake:text", environment_code="DEMO")
        self.assertFalse(ok)
        self.assertEqual(reason, "token_revoked")

    def test_contract_catches_missing_required_field(self) -> None:
        result = validate_contract({"summary": "Leak", "priority": "P1"})
        self.assertFalse(result["valid"])
        self.assertIn("missing_required:trade", result["errors"])

    def test_environment_aliases_normalize(self) -> None:
        draft = {"summary": "Too hot", "priority": "urgent", "trade": "water", "building": "arc building", "confidence": 0.8}
        result = validate_environment(draft, self.environment)
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized"]["priority"], "P1")
        self.assertEqual(result["normalized"]["trade"], "PLUMBING")
        self.assertEqual(result["normalized"]["building"], "ARC")

    def test_logger_redacts_private_payload(self) -> None:
        event = build_event(endpoint="intake:text", token_prefix="cmms_free_demo", environment_code="DEMO", status="ok", payload={"text": "private request", "safe": "metadata"})
        self.assertTrue(event["payload"]["text"].startswith("[redacted:"))
        self.assertEqual(event["payload"]["safe"], "metadata")

    def test_intake_pipeline_returns_reviewable_draft(self) -> None:
        raw, token = issue_free_token(environment_code="DEMO", scopes=["intake:text", "contracts:validate"])
        result = run_text_intake(raw_token=raw, token=token, environment=self.environment, text="There is a water leak in ARC room 205. It looks urgent.")
        self.assertTrue(result["ok"])
        self.assertEqual(result["draft"]["building"], "ARC")
        self.assertEqual(result["draft"]["trade"], "PLUMBING")
        self.assertEqual(result["next_action"], "review_before_cmms_write")
        self.assertTrue(result["audit_event"]["payload"]["text"].startswith("[redacted:"))
        self.assertTrue(result["audit_event"]["payload"]["draft"]["summary"].startswith("[redacted:"))

    def test_targeted_analytics_summary(self) -> None:
        events = [
            {"endpoint": "intake:text", "status": "ok", "environment_code": "DEMO"},
            {"endpoint": "intake:text", "status": "validation_warning", "environment_code": "DEMO"},
            {"endpoint": "contracts:validate", "status": "ok", "environment_code": "DEMO"},
        ]
        summary = summarize_events(events)
        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["by_endpoint"]["intake:text"], 2)
        self.assertTrue(summary["recommendations"])


if __name__ == "__main__":
    unittest.main()
