import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.environments import import_code_rows, seed_default_environment


class TechnicianRosterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def import_roster(self, rows: list[dict[str, str]]) -> None:
        import_code_rows("DEFAULT", "technician_roster", rows, replace=True)

    def test_tonight_hvac_request_resolves_single_on_duty_technician(self) -> None:
        from app.technician_roster import resolve_assignment_context

        self.import_roster(
            [
                {
                    "code": "TECH-100",
                    "label": "Nina Night",
                    "aliases": "Nina,Night HVAC",
                    "metadata_json": json.dumps(
                        {
                            "shift": "night",
                            "trades": ["HVAC"],
                            "assign_to": "Nina Night",
                            "issue_to": "100",
                            "job_type": "Maintenance",
                        }
                    ),
                }
            ]
        )

        context = resolve_assignment_context(
            "Create a high priority AHU-3 work order and assign it to tonight's on-duty technician.",
            "DEFAULT",
            trade="HVAC",
        )

        self.assertEqual(context["schema"], "cmms_assignment_context_v1")
        self.assertEqual(context["status"], "resolved")
        self.assertFalse(context["requires_review"])
        self.assertEqual(context["technician"]["code"], "TECH-100")
        self.assertEqual(context["assignment"]["assign_to"], "Nina Night")
        self.assertEqual(context["assignment"]["issue_to"], "100")
        self.assertEqual(context["assignment"]["job_type"], "Maintenance")

    def test_multiple_eligible_night_technicians_require_review(self) -> None:
        from app.technician_roster import resolve_assignment_context

        self.import_roster(
            [
                {
                    "code": "TECH-100",
                    "label": "Nina Night",
                    "aliases": "",
                    "metadata_json": json.dumps({"shift": "night", "trades": ["HVAC"], "assign_to": "Nina Night"}),
                },
                {
                    "code": "TECH-200",
                    "label": "Omar Overnight",
                    "aliases": "",
                    "metadata_json": json.dumps({"shift": "night", "trades": ["HVAC"], "assign_to": "Omar Overnight"}),
                },
            ]
        )

        context = resolve_assignment_context("Assign to tonight's on-duty technician.", "DEFAULT", trade="HVAC")

        self.assertEqual(context["status"], "ambiguous")
        self.assertTrue(context["requires_review"])
        self.assertIsNone(context["assignment"]["assign_to"])
        self.assertEqual([candidate["code"] for candidate in context["candidates"]], ["TECH-100", "TECH-200"])

    def test_no_roster_rows_is_not_configured(self) -> None:
        from app.technician_roster import resolve_assignment_context

        context = resolve_assignment_context("Assign to tonight's on-duty technician.", "DEFAULT", trade="HVAC")

        self.assertEqual(context["status"], "not_configured")
        self.assertFalse(context["enabled"])
        self.assertTrue(context["requires_review"])

    def test_request_without_assignment_intent_is_skipped(self) -> None:
        from app.technician_roster import resolve_assignment_context

        context = resolve_assignment_context("Create a high priority AHU-3 work order.", "DEFAULT", trade="HVAC")

        self.assertEqual(context["status"], "skipped")
        self.assertFalse(context["requires_review"])
        self.assertIn("No assignment intent", context["reasons"][0])


if __name__ == "__main__":
    unittest.main()
