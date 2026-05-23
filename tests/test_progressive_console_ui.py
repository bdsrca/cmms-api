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
