import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CmmsConnectorUiTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_cmms_connector_tab_loads_recent_push_events(self) -> None:
        html = self.portal_source()

        self.assertIn("cmmsPushEvents", html)
        self.assertIn("/cmms-connector/push-events", html)
        self.assertIn("Recent Push Events", html)
        self.assertIn("renderCmmsPushEvents", html)

    def test_cmms_connector_tab_has_manual_probe_control(self) -> None:
        html = self.portal_source()

        self.assertIn("probeCmmsConnector", html)
        self.assertIn("/cmms-connector/probe", html)
        self.assertIn("Probe", html)


if __name__ == "__main__":
    unittest.main()
