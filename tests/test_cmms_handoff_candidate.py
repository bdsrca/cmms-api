import unittest
from pathlib import Path

from app.intake_handoff import build_cmms_handoff_candidate, build_environment_handoff_preview

ROOT = Path(__file__).resolve().parents[1]


class CmmsHandoffCandidateTests(unittest.TestCase):
    def test_candidate_uses_reviewed_metadata_and_persisted_extraction_fields(self) -> None:
        run = {
            "run_id": "run_20260522_120000_deadbeef",
            "environment_code": "DEFAULT",
            "source": "email_api",
            "steps": [
                {
                    "step_name": "model_extraction",
                    "output_json": {
                        "request_type": "HVAC",
                        "confidence": 0.86,
                        "fields": {
                            "summary": "Air conditioner is too warm.",
                            "building": "ARC",
                            "room": "205",
                            "priority": "NORMAL",
                        },
                    },
                }
            ],
        }
        review = {
            "submission": {
                "submitted_by": "Leon",
                "submitted_email": "leon@example.com",
                "submitted_phone": "416-555-0199",
                "submitted_at": "2026-05-22T12:00:00Z",
                "submitted_method": "email_api",
            },
            "request": {
                "requested_due": "2026-05-25",
                "location": {"building": "ARC", "room": "207"},
            },
            "metadata_review": {
                "reviewed": True,
                "corrected_fields": ["request.location.room"],
            },
        }

        candidate = build_cmms_handoff_candidate(run, review)

        self.assertEqual(candidate["kind"], "cmms_work_order_candidate")
        self.assertEqual(candidate["safety"]["cmms_write_back"], False)
        self.assertEqual(candidate["metadata_review"], review["metadata_review"])
        self.assertEqual(
            candidate["payload"],
            {
                "summary": "Air conditioner is too warm.",
                "building": "ARC",
                "room": "207",
                "priority": "NORMAL",
                "work_order_type": "HVAC",
                "assign_to": None,
                "issue_to": None,
                "job_type": None,
                "requested_due": "2026-05-25",
                "submitted_by": "Leon",
                "submitted_email": "leon@example.com",
                "submitted_phone": "416-555-0199",
                "submitted_at": "2026-05-22T12:00:00Z",
                "submitted_method": "email_api",
            },
        )
        self.assertEqual(
            candidate["cmms_payload_preview"],
            {
                "schema": "canonical_cmms_work_order_v1",
                "fields": {
                    "summary": "Air conditioner is too warm.",
                    "location": {"building": "ARC", "room": "207"},
                    "priority": "NORMAL",
                    "work_order_type": "HVAC",
                    "assignment": {
                        "assign_to": None,
                        "issue_to": None,
                        "job_type": None,
                    },
                    "requester": {
                        "name": "Leon",
                        "email": "leon@example.com",
                        "phone": "416-555-0199",
                    },
                    "requested_due_date": "2026-05-25",
                    "source": {
                        "method": "email_api",
                        "submitted_at": "2026-05-22T12:00:00Z",
                        "intake_run_id": "run_20260522_120000_deadbeef",
                    },
                },
            },
        )
        self.assertEqual(candidate["environment_handoff_preview"]["schema"], "environment_cmms_handoff_v1")
        self.assertEqual(candidate["environment_handoff_preview"]["environment_code"], "DEFAULT")
        self.assertEqual(candidate["environment_handoff_preview"]["fields"]["requester_name"], "Leon")
        self.assertEqual(candidate["environment_handoff_preview"]["fields"]["requested_due_date"], "2026-05-25")

    def test_environment_preview_maps_canonical_payload_and_marks_needs_review(self) -> None:
        canonical_preview = {
            "schema": "canonical_cmms_work_order_v1",
            "fields": {
                "summary": "Air conditioner is too warm.",
                "location": {"building": "ARC", "room": "207"},
                "priority": "NORMAL",
                "work_order_type": "HVAC",
                "assignment": {"assign_to": None, "issue_to": None, "job_type": None},
                "requester": {
                    "name": "Leon",
                    "email": "leon@example.com",
                    "phone": "416-555-0199",
                },
                "requested_due_date": "2026-05-25",
                "source": {
                    "method": "email_api",
                    "submitted_at": "2026-05-22T12:00:00Z",
                    "intake_run_id": "run_20260522_120000_deadbeef",
                },
            },
        }

        def fake_get_environment_values(environment_code: str) -> dict[str, list[str]]:
            self.assertEqual(environment_code, "DEFAULT")
            return {"rooms": ["205"]}

        def fake_validate(environment_code: str, fields: dict[str, object]) -> dict[str, object]:
            self.assertEqual(environment_code, "DEFAULT")
            self.assertEqual(fields["room"], "207")
            return {
                "valid": True,
                "errors": [],
                "warnings": [
                    {
                        "field": "room",
                        "value": "207",
                        "message": "Room 207 is not in configured room codes.",
                    }
                ],
                "normalized": {
                    "building": "ARC",
                    "priority": "NORMAL",
                    "work_order_type": "HVAC",
                },
            }

        preview = build_environment_handoff_preview(
            canonical_preview,
            "DEFAULT",
            get_environment_values_func=fake_get_environment_values,
            validate_func=fake_validate,
        )

        self.assertEqual(preview["schema"], "environment_cmms_handoff_v1")
        self.assertEqual(preview["environment_code"], "DEFAULT")
        self.assertEqual(preview["status"], "needs_review")
        self.assertEqual(
            preview["fields"],
            {
                "summary": "Air conditioner is too warm.",
                "building": "ARC",
                "room": "207",
                "priority": "NORMAL",
                "work_order_type": "HVAC",
                "assign_to": None,
                "issue_to": None,
                "job_type": None,
                "requester_name": "Leon",
                "requester_email": "leon@example.com",
                "requester_phone": "416-555-0199",
                "requested_due_date": "2026-05-25",
                "source_method": "email_api",
                "intake_run_id": "run_20260522_120000_deadbeef",
            },
        )
        self.assertEqual(preview["validation"]["valid"], False)
        self.assertIn("Room 207 is not in configured room codes.", preview["validation"]["warnings"])
        self.assertIn("Assign To is empty.", preview["validation"]["warnings"])
        self.assertIn("Issue To is empty.", preview["validation"]["warnings"])
        self.assertIn("Job Type is empty.", preview["validation"]["warnings"])
        self.assertEqual(
            preview["validation"]["normalized"],
            {"building": "ARC", "priority": "NORMAL", "work_order_type": "HVAC"},
        )

    def test_environment_preview_blocks_invalid_environment(self) -> None:
        canonical_preview = {"schema": "canonical_cmms_work_order_v1", "fields": {"summary": "Test"}}

        def fake_get_environment_values(environment_code: str) -> dict[str, list[str]]:
            raise ValueError("Invalid or disabled environment_code")

        preview = build_environment_handoff_preview(
            canonical_preview,
            "MISSING",
            get_environment_values_func=fake_get_environment_values,
            validate_func=lambda environment_code, fields: {"valid": True, "errors": [], "warnings": [], "normalized": {}},
        )

        self.assertEqual(preview["schema"], "environment_cmms_handoff_v1")
        self.assertEqual(preview["environment_code"], "MISSING")
        self.assertEqual(preview["status"], "blocked")
        self.assertEqual(preview["validation"]["valid"], False)
        self.assertIn("Invalid or disabled environment_code", preview["validation"]["errors"])

    def test_candidate_route_is_admin_and_review_gated(self) -> None:
        operations_source = (ROOT / "app" / "operations_routes.py").read_text(encoding="utf-8")
        ui_source = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn("/api/admin/workflow-runs/{run_id}/cmms-handoff-candidate", operations_source)
        self.assertIn("current_admin", operations_source)
        self.assertIn("Metadata review must be applied", operations_source)
        self.assertIn("cmms-handoff-candidate", ui_source)


if __name__ == "__main__":
    unittest.main()
