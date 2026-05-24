from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def portal_source() -> str:
    return (ROOT / "app" / "ui.py").read_text(encoding="utf-8")


def test_progressive_console_navigation_groups_are_declared() -> None:
    html = portal_source()

    assert "const menuGroups = [" in html
    assert '"Operate"' in html
    assert '"Configure"' in html
    assert '"Quality"' in html
    assert '"Admin"' in html
    assert 'class="nav-group-title"' in html


def test_progressive_console_page_shell_supports_subtitles() -> None:
    html = portal_source()

    assert 'function pageShell(title, html, actions = "", subtitle = "")' in html
    assert "pageSubtitle" in html
    assert "page-title-main" in html


def test_progressive_console_dropdown_style_is_available() -> None:
    html = portal_source()

    assert ".select-wrap" in html
    assert ".select-wrap::after" in html
    assert ".cmms-select" in html
    assert 'class="cmms-select"' in html


def test_dashboard_uses_progressive_summary_panels() -> None:
    html = portal_source()

    assert "dashboard-hero" in html
    assert "dashboard-status-list" in html
    assert "Regression Health" in html


def test_ui_audit_polish_selectors_are_available() -> None:
    html = portal_source()

    assert "width: 100%;" in html
    assert "grid-column: 1 / -1;" in html
    assert ".mobile-menu-toggle" in html
    assert ".nav-open" in html
    assert ".admin-badge" in html
    assert "coming-soon-tabs" in html
    assert "credentials-panel" in html
    assert "Test API credentials" in html


def test_core_pages_have_subtitles() -> None:
    html = portal_source()

    assert 'pageShell("Test Console"' in html
    assert "Run advisory AI endpoints" in html
    assert "Turn pasted maintenance emails" in html
    assert "Compose controlled API calls" in html
    assert "Manage environment-specific codes" in html


def test_dense_pages_are_quieter_by_default() -> None:
    html = portal_source()

    assert "dashboard-regression-details" in html
    assert "Regression details" in html
    assert "table-scroll" in html
    assert "quiet-toolbar" in html
    assert "Review saved cases" in html
    assert "Manage generated API keys" in html


def test_voice_input_is_icon_first_with_collapsed_settings() -> None:
    html = portal_source()

    assert "voice-icon-button" in html
    assert "voiceSettings" in html
    assert "Voice settings" in html
    assert 'aria-label="Start voice input"' in html
    assert "startVoiceRecognition()" in html


def test_primary_console_textareas_are_roomier() -> None:
    html = portal_source()

    assert ".test-console-textarea { min-height: 180px; }" in html
    assert ".orchestration-textarea { min-height: 180px; }" in html
    assert 'id="tText" class="compact-textarea test-console-textarea"' in html
    assert 'id="oText" class="compact-textarea orchestration-textarea"' in html


def test_test_console_actions_use_roomier_button_grid() -> None:
    html = portal_source()

    assert ".test-console-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in html
    assert 'class="compact-actions test-console-actions"' in html


def test_test_console_output_can_be_hidden_or_cleared() -> None:
    html = portal_source()

    assert ".console-output { max-height:" in html
    assert 'outputToolbar("tOut", { hide: true, clear: true })' in html
    assert "function collapseOutputPanel(id)" in html
    assert "function clearConsoleOutput(id)" in html
