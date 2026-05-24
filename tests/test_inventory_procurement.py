import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.demo_environment import seed_demo_environment
from app.environments import import_code_rows


def work_order_plan_with_filter() -> dict:
    return {
        "schema": "cmms_work_order_plan_v1",
        "status": "planned",
        "asset_code": "AHU-3",
        "likely_parts": [
            {
                "part_number": "FILTER-AHU-20X25X2",
                "description": "20x25x2 AHU filter",
                "quantity": 4,
                "unit": "EA",
            }
        ],
    }


class InventoryProcurementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_demo_environment("DEFAULT")

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_inventory_context_detects_filter_shortage_from_environment_parts(self) -> None:
        from app.inventory_procurement import resolve_inventory_context

        context = resolve_inventory_context(work_order_plan_with_filter(), "DEFAULT")

        self.assertEqual(context["schema"], "cmms_inventory_context_v1")
        self.assertEqual(context["status"], "shortage")
        self.assertTrue(context["requires_procurement"])
        self.assertEqual(context["items"][0]["part_number"], "FILTER-AHU-20X25X2")
        self.assertEqual(context["items"][0]["required_quantity"], 4)
        self.assertEqual(context["items"][0]["quantity_on_hand"], 0)
        self.assertEqual(context["items"][0]["shortage_quantity"], 4)

    def test_procurement_request_explains_why_purchase_is_needed(self) -> None:
        from app.inventory_procurement import build_procurement_request, resolve_inventory_context

        inventory_context = resolve_inventory_context(work_order_plan_with_filter(), "DEFAULT")
        procurement = build_procurement_request("run-123", "DEFAULT", work_order_plan_with_filter(), inventory_context)

        self.assertEqual(procurement["schema"], "cmms_procurement_request_v1")
        self.assertEqual(procurement["status"], "drafted")
        self.assertTrue(procurement["advisory_only"])
        self.assertEqual(procurement["asset_code"], "AHU-3")
        self.assertEqual(procurement["lines"][0]["part_number"], "FILTER-AHU-20X25X2")
        self.assertEqual(procurement["lines"][0]["quantity"], 12)
        self.assertIn("0 on hand", procurement["reason"])
        self.assertIn("shortage of 4", procurement["reason"])

    def test_inventory_context_reports_available_parts_without_procurement(self) -> None:
        from app.inventory_procurement import build_procurement_request, resolve_inventory_context

        import_code_rows(
            "DEFAULT",
            "custom:inventory_parts",
            [
                {
                    "code": "FILTER-AHU-20X25X2",
                    "label": "20x25x2 AHU filter",
                    "aliases": "AHU filter",
                    "metadata_json": json.dumps({"quantity_on_hand": 8, "reorder_quantity": 12, "unit": "EA"}),
                }
            ],
            replace=True,
        )

        inventory_context = resolve_inventory_context(work_order_plan_with_filter(), "DEFAULT")
        procurement = build_procurement_request("run-123", "DEFAULT", work_order_plan_with_filter(), inventory_context)

        self.assertEqual(inventory_context["status"], "available")
        self.assertFalse(inventory_context["requires_procurement"])
        self.assertEqual(procurement["status"], "not_required")
        self.assertEqual(procurement["lines"], [])


if __name__ == "__main__":
    unittest.main()
