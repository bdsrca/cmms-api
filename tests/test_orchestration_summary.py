import unittest


def sample_contexts() -> dict:
    return {
        "asset_context": {
            "status": "resolved",
            "asset": {"code": "AHU-3", "label": "Air Handler Unit 3"},
        },
        "assignment_context": {
            "status": "resolved",
            "technician": {"code": "TECH-100", "label": "Nina Night", "shift": "night"},
            "assignment": {"assign_to": "Nina Night", "issue_to": "100", "job_type": "Maintenance"},
        },
        "inventory_context": {
            "status": "shortage",
            "requires_procurement": True,
            "items": [
                {
                    "part_number": "FILTER-AHU-20X25X2",
                    "description": "20x25x2 AHU filter",
                    "required_quantity": 4,
                    "quantity_on_hand": 0,
                    "shortage_quantity": 4,
                    "status": "shortage",
                }
            ],
        },
        "procurement_request": {
            "status": "drafted",
            "lines": [{"part_number": "FILTER-AHU-20X25X2", "quantity": 12}],
            "reason": "Procurement draft created for asset AHU-3 because FILTER-AHU-20X25X2 needs 4, 0 on hand, shortage of 4.",
        },
        "action_plan": {
            "actions": [
                {"action_id": "create_work_order", "status": "dry_run", "requires_review": False},
                {"action_id": "assign_work_order", "status": "dry_run", "requires_review": False},
                {"action_id": "create_purchase_request", "status": "dry_run", "requires_review": False},
            ]
        },
        "cmms_push": {"status": "dry_run", "blocked_reasons": []},
    }


class OrchestrationSummaryTests(unittest.TestCase):
    def test_build_summary_for_full_work_order_assignment_inventory_and_procurement_flow(self) -> None:
        from app.orchestration_summary import build_orchestration_summary

        contexts = sample_contexts()
        summary = build_orchestration_summary(
            run_id="run-123",
            environment_code="DEFAULT",
            priority="URGENT",
            work_order_type="HVAC",
            **contexts,
        )

        self.assertEqual(summary["schema"], "cmms_orchestration_summary_v1")
        self.assertEqual(summary["status"], "dry_run")
        self.assertEqual(summary["asset_code"], "AHU-3")
        self.assertEqual(summary["priority"], "URGENT")
        self.assertEqual(summary["work_order_type"], "HVAC")
        self.assertEqual(
            summary["requested_actions"],
            ["create_work_order", "assign_work_order", "check_inventory", "create_purchase_request"],
        )
        self.assertEqual(summary["steps"]["work_order"]["status"], "dry_run")
        self.assertEqual(summary["steps"]["assignment"]["technician"], "Nina Night")
        self.assertEqual(summary["steps"]["inventory"]["status"], "shortage")
        self.assertTrue(summary["steps"]["inventory"]["requires_procurement"])
        self.assertEqual(summary["steps"]["procurement"]["status"], "dry_run")
        self.assertEqual(summary["dry_run_actions"], ["create_work_order", "assign_work_order", "create_purchase_request"])
        self.assertFalse(summary["human_review_required"])
        self.assertIn("AHU-3", summary["operator_message"])
        self.assertIn("Nina Night", summary["operator_message"])
        self.assertIn("purchase request", summary["operator_message"])

    def test_summary_marks_needs_review_when_any_action_or_context_requires_review(self) -> None:
        from app.orchestration_summary import build_orchestration_summary

        contexts = sample_contexts()
        contexts["assignment_context"] = {"status": "ambiguous", "requires_review": True, "reasons": ["Multiple technicians matched."]}
        contexts["action_plan"] = {"actions": [{"action_id": "assign_work_order", "status": "needs_review", "requires_review": True}]}
        contexts["cmms_push"] = {"status": "blocked", "blocked_reasons": ["human_review_required"]}

        summary = build_orchestration_summary(
            run_id="run-123",
            environment_code="DEFAULT",
            priority="URGENT",
            work_order_type="HVAC",
            **contexts,
        )

        self.assertEqual(summary["status"], "needs_review")
        self.assertTrue(summary["human_review_required"])
        self.assertIn("human_review_required", summary["blocked_reasons"])
        self.assertIn("Multiple technicians matched.", summary["review_reasons"])


if __name__ == "__main__":
    unittest.main()
