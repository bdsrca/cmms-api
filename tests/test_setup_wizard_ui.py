import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SetupWizardUiTests(unittest.TestCase):
    def portal_source(self) -> str:
        return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")

    def test_setup_wizard_navigation_and_actions_are_present(self) -> None:
        html = self.portal_source()

        self.assertIn('"setup","Setup Wizard",true', html)
        self.assertIn('["users", "remote", "system", "setup"]', html)
        self.assertIn("async function setupWizard()", html)
        self.assertIn("refreshSetupStatus()", html)
        self.assertIn("createSystemBackup()", html)
        self.assertIn("downloadLatestBackupManifest()", html)

    def test_setup_wizard_calls_admin_setup_and_backup_endpoints(self) -> None:
        html = self.portal_source()

        self.assertIn('api("/api/admin/setup/status")', html)
        self.assertIn('api("/api/admin/system/backup"', html)
        self.assertIn('api("/api/admin/system/backups")', html)
        self.assertIn("Download Latest Backup Manifest", html)


if __name__ == "__main__":
    unittest.main()
