import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowRunDetailUiTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_logs_table_opens_workflow_run_detail(self) -> None:
        html = self.portal_source()

        self.assertIn("View Run", html)
        self.assertIn("renderWorkflowRunDetail(trace)", html)
        self.assertIn("Workflow Run Detail", html)

    def test_workflow_run_detail_surfaces_gate_panels(self) -> None:
        html = self.portal_source()

        self.assertIn("renderTraceStepPanel(trace, \"output_contract_validation\"", html)
        self.assertIn("renderTraceStepPanel(trace, \"code_normalization_suggestion_agent\"", html)
        self.assertIn("renderTraceStepPanel(trace, \"environment_validation\"", html)
        self.assertIn("renderTraceStepPanel(trace, \"safety_review\"", html)
        self.assertIn("renderTraceStepPanel(trace, \"cmms_auto_push\"", html)
        self.assertIn("CMMS Push Gate", html)


if __name__ == "__main__":
    unittest.main()
