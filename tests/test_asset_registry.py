import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.environments import import_code_rows, seed_default_environment


class AssetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def import_assets(self, rows: list[dict[str, str]]) -> None:
        import_code_rows("DEFAULT", "assets", rows, replace=True)

    def test_exact_asset_code_resolves_with_parts_planning_hints(self) -> None:
        from app.asset_registry import resolve_asset_context

        self.import_assets(
            [
                {
                    "code": "AHU-3",
                    "label": "Air Handler Unit 3",
                    "aliases": "AHU 3,Air Handler 3",
                    "metadata_json": json.dumps(
                        {
                            "asset_type": "Air Handler Unit",
                            "building": "ARC",
                            "room": "MECH-1",
                            "trade": "HVAC",
                            "work_order_type": "HVAC",
                            "parts": [
                                {
                                    "part_number": "FILTER-AHU-20X25X2",
                                    "description": "20x25x2 AHU filter",
                                    "quantity": 4,
                                    "unit": "EA",
                                }
                            ],
                        }
                    ),
                }
            ]
        )

        context = resolve_asset_context("Create a high priority work order for AHU-3 filters.", "DEFAULT")

        self.assertEqual(context["schema"], "cmms_asset_context_v1")
        self.assertEqual(context["status"], "resolved")
        self.assertFalse(context["requires_review"])
        self.assertEqual(context["asset"]["code"], "AHU-3")
        self.assertEqual(context["asset"]["asset_type"], "Air Handler Unit")
        self.assertEqual(context["asset"]["building"], "ARC")
        self.assertEqual(context["planning_hints"]["trade"], "HVAC")
        self.assertEqual(context["planning_hints"]["work_order_type"], "HVAC")
        self.assertEqual(context["planning_hints"]["likely_parts"][0]["part_number"], "FILTER-AHU-20X25X2")

    def test_ambiguous_asset_alias_requires_review(self) -> None:
        from app.asset_registry import resolve_asset_context

        self.import_assets(
            [
                {"code": "AHU-3-E", "label": "AHU 3 East", "aliases": "AHU-3", "metadata_json": "{}"},
                {"code": "AHU-3-W", "label": "AHU 3 West", "aliases": "AHU-3", "metadata_json": "{}"},
            ]
        )

        context = resolve_asset_context("Inspect AHU-3 filters.", "DEFAULT")

        self.assertEqual(context["status"], "ambiguous")
        self.assertTrue(context["requires_review"])
        self.assertIsNone(context["asset"])
        self.assertEqual([candidate["code"] for candidate in context["candidates"]], ["AHU-3-E", "AHU-3-W"])

    def test_missing_environment_skips_asset_resolution(self) -> None:
        from app.asset_registry import resolve_asset_context

        context = resolve_asset_context("Inspect AHU-3 filters.", None)

        self.assertEqual(context["status"], "skipped")
        self.assertFalse(context["enabled"])
        self.assertIn("No environment_code", context["reasons"][0])

    def test_no_configured_assets_is_not_configured(self) -> None:
        from app.asset_registry import resolve_asset_context

        context = resolve_asset_context("Inspect AHU-3 filters.", "DEFAULT")

        self.assertEqual(context["status"], "not_configured")
        self.assertFalse(context["enabled"])
        self.assertTrue(context["requires_review"])
