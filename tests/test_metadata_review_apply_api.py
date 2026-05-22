import unittest
from pathlib import Path

from app.intake_metadata_reviews import apply_metadata_review_patch

ROOT = Path(__file__).resolve().parents[1]


class MetadataReviewApplyApiTests(unittest.TestCase):
    def test_apply_patch_updates_reviewable_fields_and_tracks_corrections(self) -> None:
        original = {
            "submission": {
                "submitted_by": "Leon",
                "submitted_email": "leon@example.com",
                "submitted_phone": "1234",
                "submitted_at": "2026-05-22T14:30:00Z",
                "submitted_method": "manual",
            },
            "request": {
                "requested_due": "2026-05-23",
                "requested_due_raw": "by tomorrow",
                "location": {"building": "ARC", "room": "205", "area": None, "raw": "ARC 205"},
                "location_conflict": False,
            },
        }

        reviewed = apply_metadata_review_patch(
            original,
            {
                "submitted_by": "Leon",
                "submitted_email": "leon@example.com",
                "submitted_phone": "416-555-0199",
                "requested_due": "2026-05-25",
                "building": "ARC",
                "room": "207",
            },
        )

        self.assertEqual(reviewed["submission"]["submitted_phone"], "416-555-0199")
        self.assertEqual(reviewed["submission"]["submitted_method"], "manual")
        self.assertEqual(reviewed["request"]["requested_due_raw"], "by tomorrow")
        self.assertEqual(reviewed["request"]["location"]["room"], "207")
        self.assertEqual(
            reviewed["metadata_review"],
            {
                "reviewed": True,
                "corrected_fields": [
                    "submission.submitted_phone",
                    "request.requested_due",
                    "request.location.room",
                ],
            },
        )

    def test_review_apply_route_and_storage_are_controlled(self) -> None:
        operations_source = (ROOT / "app" / "operations_routes.py").read_text(encoding="utf-8")
        endpoint_source = (ROOT / "app" / "ai_endpoints.py").read_text(encoding="utf-8")
        db_source = (ROOT / "app" / "db.py").read_text(encoding="utf-8")
        ui_source = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('/api/admin/workflow-runs/{run_id}/metadata-review"', operations_source)
        self.assertIn("/api/admin/workflow-runs/{run_id}/metadata-review/apply", operations_source)
        self.assertIn("current_admin", operations_source)
        self.assertIn('run["metadata_review"]', operations_source)
        self.assertIn("metadata_review_record", operations_source)
        self.assertIn("save_extracted_metadata_review", endpoint_source)
        self.assertIn("CREATE TABLE IF NOT EXISTS intake_metadata_reviews", db_source)
        self.assertIn("/metadata-review/apply", ui_source)
        self.assertIn("renderTraceMetadataReview", ui_source)


if __name__ == "__main__":
    unittest.main()
