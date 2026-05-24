import unittest


def resolved_assignment_context() -> dict:
    return {
        "schema": "cmms_assignment_context_v1",
        "status": "resolved",
        "requires_review": False,
        "technician": {"code": "TECH-100", "label": "Nina Night"},
        "assignment": {"assign_to": "Nina Night", "issue_to": "100", "job_type": "Maintenance"},
        "reasons": ["Matched on-duty technician TECH-100."],
    }


class CmmsActionPlanTests(unittest.TestCase):
    def test_initial_plan_has_create_and_assign_actions_with_idempotency_keys(self) -> None:
        from app.cmms_action_plan import build_initial_action_plan

        plan = build_initial_action_plan("run-123", "DEFAULT", resolved_assignment_context())

        self.assertEqual(plan["schema"], "cmms_action_plan_v1")
        self.assertEqual(plan["run_id"], "run-123")
        self.assertEqual([action["action_id"] for action in plan["actions"]], ["create_work_order", "assign_work_order"])
        self.assertEqual(plan["actions"][0]["status"], "planned")
        self.assertEqual(plan["actions"][0]["idempotency_key"], "cmms-run-run-123-create-work-order")
        self.assertEqual(plan["actions"][1]["status"], "ready")
        self.assertEqual(plan["actions"][1]["assignment"]["assign_to"], "Nina Night")

    def test_assignment_action_needs_review_when_roster_is_ambiguous(self) -> None:
        from app.cmms_action_plan import build_initial_action_plan

        plan = build_initial_action_plan(
            "run-123",
            "DEFAULT",
            {
                "schema": "cmms_assignment_context_v1",
                "status": "ambiguous",
                "requires_review": True,
                "assignment": {"assign_to": None, "issue_to": None, "job_type": None},
                "reasons": ["Multiple configured technicians matched."],
            },
        )

        self.assertEqual(plan["actions"][1]["status"], "needs_review")
        self.assertTrue(plan["actions"][1]["requires_review"])
        self.assertIn("Multiple configured technicians matched.", plan["actions"][1]["reasons"])

    def test_final_plan_marks_create_and_assign_succeeded_only_after_sent_push(self) -> None:
        from app.cmms_action_plan import build_initial_action_plan, finalize_action_plan

        plan = finalize_action_plan(
            build_initial_action_plan("run-123", "DEFAULT", resolved_assignment_context()),
            {"status": "sent", "external_reference": "WO-456"},
        )

        self.assertEqual(plan["actions"][0]["status"], "succeeded")
        self.assertEqual(plan["actions"][0]["external_reference"], "WO-456")
        self.assertEqual(plan["actions"][1]["status"], "succeeded")
        self.assertEqual(plan["actions"][1]["method"], "included_in_create_payload")

    def test_final_plan_blocks_assignment_when_create_is_blocked(self) -> None:
        from app.cmms_action_plan import build_initial_action_plan, finalize_action_plan

        plan = finalize_action_plan(
            build_initial_action_plan("run-123", "DEFAULT", resolved_assignment_context()),
            {"status": "blocked", "blocked_reasons": ["handoff_not_ready"]},
        )

        self.assertEqual(plan["actions"][0]["status"], "blocked")
        self.assertEqual(plan["actions"][1]["status"], "blocked")
        self.assertIn("create_work_order_not_succeeded", plan["actions"][1]["reasons"])


if __name__ == "__main__":
    unittest.main()
