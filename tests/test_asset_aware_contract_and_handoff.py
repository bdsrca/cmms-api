import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.environments import seed_default_environment
from app.intake_handoff import build_canonical_cmms_payload_preview, build_cmms_handoff_candidate
from app.output_contracts import seed_default_output_contracts, validate_output_contract


def sample_asset_context() -> dict:
    return {
        "schema": "cmms_asset_context_v1",
        "environment_code": "DEFAULT",
        "enabled": True,
        "status": "resolved",
        "requires_review": False,
        "asset": {
            "code": "AHU-3",
            "label": "Air Handler Unit 3",
            "aliases": ["AHU 3"],
            "asset_type": "Air Handler Unit",
            "building": "ARC",
            "room": "MECH-1",
            "matched_on": "AHU-3",
        },
        "candidates": [],
        "planning_hints": {
            "trade": "HVAC",
            "work_order_type": "HVAC",
            "likely_parts": [
                {
                    "part_number": "FILTER-AHU-20X25X2",
                    "description": "20x25x2 AHU filter",
                    "quantity": 4,
                    "unit": "EA",
                    "planning_only": True,
                }
            ],
        },
        "reasons": ["Matched configured asset AHU-3."],
    }


def sample_work_order_plan() -> dict:
    return {
        "schema": "cmms_work_order_plan_v1",
        "status": "planned",
        "advisory_only": True,
        "asset_code": "AHU-3",
        "trade": "HVAC",
        "work_order_type": "HVAC",
        "likely_parts": [
            {
                "part_number": "FILTER-AHU-20X25X2",
                "description": "20x25x2 AHU filter",
                "quantity": 4,
                "unit": "EA",
                "planning_only": True,
            }
        ],
        "requires_review": False,
        "reasons": ["Matched configured asset AHU-3."],
    }


def sample_payload() -> dict:
    return {
        "summary": "AHU-3 needs filters checked.",
        "building": "ARC",
        "room": "205",
        "priority": "URGENT",
        "work_order_type": "HVAC",
        "assign_to": None,
        "issue_to": None,
        "job_type": None,
        "confidence": 0.93,
        "submission": {},
        "request": {},
        "metadata_review": {"reviewed": False},
        "asset_context": sample_asset_context(),
        "work_order_plan": sample_work_order_plan(),
    }


class AssetAwareContractAndHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_patcher = patch.object(db, "DB_FILE", Path(self.tmp.name) / "test.db")
        self.db_patcher.start()
        db.init_db()
        seed_default_environment()
        seed_default_output_contracts()

    def tearDown(self) -> None:
        self.db_patcher.stop()
        self.tmp.cleanup()

    def test_default_intake_contract_accepts_asset_context_and_work_order_plan(self) -> None:
        validation = validate_output_contract("cmms-intake", sample_payload())

        self.assertTrue(validation["valid"], validation["errors"])
        self.assertEqual(validation["contract_version"], "v7")
        self.assertEqual(validation["normalized_payload"]["asset_context"]["asset"]["code"], "AHU-3")
        self.assertEqual(validation["normalized_payload"]["work_order_plan"]["asset_code"], "AHU-3")

    def test_canonical_preview_carries_asset_and_planning_metadata(self) -> None:
        preview = build_canonical_cmms_payload_preview(sample_payload(), "run-1")

        self.assertEqual(preview["fields"]["asset"]["code"], "AHU-3")
        self.assertEqual(preview["fields"]["planning"]["trade"], "HVAC")
        self.assertEqual(preview["fields"]["planning"]["likely_parts"][0]["part_number"], "FILTER-AHU-20X25X2")
        self.assertTrue(preview["fields"]["planning"]["advisory_only"])

    def test_handoff_candidate_carries_asset_context_from_workflow_trace(self) -> None:
        run = {
            "run_id": "run-asset-1",
            "environment_code": "DEFAULT",
            "source": "test",
            "steps": [
                {
                    "step_name": "model_extraction",
                    "output_json": {
                        "request_type": "HVAC",
                        "confidence": 0.93,
                        "fields": {
                            "summary": "AHU-3 needs filters checked.",
                            "building": "ARC",
                            "room": "205",
                            "priority": "URGENT",
                        },
                    },
                },
                {"step_name": "asset_resolution", "output_json": sample_asset_context()},
                {"step_name": "work_order_planning", "output_json": sample_work_order_plan()},
            ],
        }
        review = {
            "submission": {},
            "request": {"location": {"building": "ARC", "room": "205"}},
            "metadata_review": {"reviewed": False},
        }

        candidate = build_cmms_handoff_candidate(run, review)

        self.assertEqual(candidate["payload"]["asset_context"]["asset"]["code"], "AHU-3")
        self.assertEqual(candidate["payload"]["work_order_plan"]["asset_code"], "AHU-3")
        self.assertEqual(candidate["cmms_payload_preview"]["fields"]["asset"]["code"], "AHU-3")


if __name__ == "__main__":
    unittest.main()
