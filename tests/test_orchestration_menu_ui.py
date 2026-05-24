import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OrchestrationMenuUiTests(unittest.TestCase):
    def test_operator_console_has_orchestration_menu_and_renderer(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('["orchestration","Orchestration"', html)
        self.assertIn('["Operate", ["dashboard", "orchestration", "test", "email", "builder"]]', html)
        self.assertIn("const handlers = { dashboard, orchestration, test", html)
        self.assertIn("function orchestration()", html)
        self.assertIn("async function runOrchestration()", html)
        self.assertIn("/api/ai/cmms-intake", html)
        self.assertIn("renderOrchestrationSummary", html)
        self.assertIn("renderOrchestrationActions", html)
        self.assertIn("orchestration_summary", html)
        self.assertIn("create_purchase_request", html)

    def test_environment_dropdowns_select_default_local_test_first(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('const selectedEnv = state.envs.some(e => e.environment_code === "DEFAULT") ? "DEFAULT" : state.envs[0]?.environment_code;', html)
        self.assertIn('e.environment_code === selectedEnv ? "selected" : ""', html)

    def test_orchestration_and_test_console_default_to_fast_workflow_mode(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('<select id="oWorkflowMode"', html)
        self.assertIn('<select id="tWorkflowMode"', html)
        self.assertIn('workflow_mode: $("oWorkflowMode").value', html)
        self.assertIn('if (ep === "cmms-intake") body.workflow_mode = $("tWorkflowMode").value;', html)

    def test_environment_default_workflow_mode_switch_is_exposed_and_synced(self) -> None:
        html = (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

        self.assertIn('data-workflow-mode="${workflowModeForEnvironment(e)}"', html)
        self.assertIn("function syncWorkflowModeFromEnvironment(envSelectId, workflowSelectId)", html)
        self.assertIn("syncWorkflowModeFromEnvironment('oEnv', 'oWorkflowMode')", html)
        self.assertIn("syncWorkflowModeFromEnvironment('tEnv', 'tWorkflowMode')", html)
        self.assertIn('id="envDefaultWorkflowMode"', html)
        self.assertIn("patchEnvWorkflowMode", html)
        self.assertIn("default_workflow_mode", html)


if __name__ == "__main__":
    unittest.main()
