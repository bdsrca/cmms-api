# Progressive Console UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the local CMMS portal into a calmer Progressive Console with clearer page layout, grouped navigation, fewer visible controls, and modern native dropdown styling.

**Architecture:** Keep the existing FastAPI-served single-file portal in `app/ui.py`. Add small render helpers and CSS classes inside the existing template instead of introducing a frontend build system or changing API behavior.

**Tech Stack:** Python string-served HTML, vanilla JavaScript, CSS, existing pytest string/smoke tests.

---

## File Structure

- Modify: `app/ui.py`
  - CSS visual system, navigation grouping, page shell subtitle support, dashboard composition, dropdown styling.
- Modify or create: `tests/test_progressive_console_ui.py`
  - String-level checks that the UI exposes grouped navigation, progressive layout selectors, and modern dropdown selectors.

### Task 1: Add UI Contract Tests

**Files:**
- Create: `tests/test_progressive_console_ui.py`
- Read: `app/ui.py`

- [ ] **Step 1: Write failing tests for the new UI selectors**

```python
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

    assert "function pageShell(title, html, actions = \"\", subtitle = \"\")" in html
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
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```bash
pytest tests/test_progressive_console_ui.py -q
```

Expected: FAIL because `menuGroups`, subtitle shell selectors, modern select selectors, and dashboard summary selectors do not all exist yet.

### Task 2: Add Progressive Console CSS and Dropdown Styling

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_progressive_console_ui.py`

- [ ] **Step 1: Update the CSS layer**

In `app/ui.py`, update the existing modern CSS block with:

```css
.content { padding: 30px clamp(22px, 3vw, 38px); }
.page-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 22px;
}
.page-title-main { display: grid; gap: 5px; }
.page-subtitle { color: #64748b; font-size: 14px; max-width: 720px; line-height: 1.45; }
.section-stack { display: grid; gap: 18px; }
.dashboard-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(280px, .75fr);
  gap: 18px;
  align-items: stretch;
}
.dashboard-status-list { display: grid; gap: 10px; }
.status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 0;
  border-bottom: 1px solid #eef2f7;
}
.status-row:last-child { border-bottom: 0; }
.select-wrap {
  position: relative;
  display: block;
}
.select-wrap::after {
  content: "";
  position: absolute;
  right: 14px;
  top: 50%;
  width: 8px;
  height: 8px;
  border-right: 2px solid #64748b;
  border-bottom: 2px solid #64748b;
  transform: translateY(-65%) rotate(45deg);
  pointer-events: none;
}
select, .cmms-select {
  appearance: none;
  min-height: 42px;
  border-radius: 12px;
  padding: 9px 38px 9px 13px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}
select:focus, .cmms-select:focus {
  border-color: #0ea5e9;
  box-shadow: 0 0 0 4px rgba(14, 165, 233, .14);
}
details.advanced-panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fbfcfe;
  padding: 12px 14px;
}
details.advanced-panel summary {
  cursor: pointer;
  font-weight: 700;
  color: #334155;
}
@media (max-width: 900px) {
  .dashboard-hero { grid-template-columns: 1fr; }
  .page-title { display: grid; }
}
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
pytest tests/test_progressive_console_ui.py -q
```

Expected: tests still fail until render structure is updated.

### Task 3: Group Navigation and Add Page Subtitles

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_progressive_console_ui.py`

- [ ] **Step 1: Replace flat menu rendering with grouped rendering**

Add `menuGroups` near the current `menu` definition:

```javascript
const menuGroups = [
  ["Operate", [["dashboard","Dashboard",false,"..."],["test","Test Console",false,"..."],["email","Email Intake",false,"..."],["builder","API Builder",false,"..."]]],
  ["Configure", [["environments","Environments",true,"..."],["contracts","Output Contracts",true,"..."],["prompts","Prompt Versions",true,"..."],["keys","API Keys",true,"..."]]],
  ["Quality", [["testCases","Test Cases",true,"..."],["testSuites","Test Suites",true,"..."],["logs","Logs",false,"..."],["reports","Reports",false,"..."],["kb","Knowledge Base",false,"..."]]],
  ["Admin", [["users","Users",true,"..."],["remote","Remote Access",true,"..."],["system","System",true,"..."]]]
];
const menu = menuGroups.flatMap(group => group[1]);
```

Keep the existing icon values from the old menu when applying this change.

- [ ] **Step 2: Update `renderNav()`**

Render each group title and visible menu item:

```javascript
function renderNav() {
  $("nav").innerHTML = menuGroups.map(([group, items]) => {
    const visible = items.filter(([, , admin]) => !admin || state.me?.role === "admin");
    if (!visible.length) return "";
    return `<div class="nav-group"><div class="nav-group-title">${group}</div>${visible.map(([id,label,admin,icon]) =>
      `<button class="${state.page===id?'active':''} ${admin?'admin-only':''}" onclick="show('${id}')"><span class="cmms-nav-icon">${icon}</span><span>${label}</span></button>`
    ).join("")}</div>`;
  }).join("");
}
```

- [ ] **Step 3: Update `pageShell()`**

Change it to accept a subtitle:

```javascript
function pageShell(title, html, actions = "", subtitle = "") {
  $("pageTitle").textContent = title;
  $("pageActions").innerHTML = actions;
  const subtitleEl = $("pageSubtitle");
  if (subtitleEl) subtitleEl.textContent = subtitle;
  $("page").innerHTML = html;
  renderNav();
}
```

Update the header markup to include:

```html
<div class="page-title-main"><h1 id="pageTitle">Dashboard</h1><div id="pageSubtitle" class="page-subtitle"></div></div>
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_progressive_console_ui.py -q
```

Expected: navigation and page shell tests pass; dashboard/dropdown tests may still fail.

### Task 4: Apply Dashboard and Dropdown Layout Polish

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_progressive_console_ui.py`

- [ ] **Step 1: Recompose `dashboard()`**

Replace the equal metric grid with a progressive summary:

```javascript
pageShell("Dashboard", `<div class="section-stack">
  <div class="dashboard-hero">
    <div class="card"><h2>Control plane readiness</h2><div class="card-body">
      <div class="metric">${state.envs.length} environments</div>
      <p class="muted">Local advisory workflow with deterministic validation gates.</p>
    </div></div>
    <div class="card"><h2>System status</h2><div class="card-body dashboard-status-list">
      <div class="status-row"><span>API keys</span><strong>${state.keys.length}</strong></div>
      <div class="status-row"><span>Current role</span><strong>${state.me.role}</strong></div>
      <div class="status-row"><span>Model runtime</span><strong>Local</strong></div>
    </div></div>
  </div>
  <div class="card"><h2>Safety posture</h2><div class="card-body">Advisory mode only. No CMMS write-back, work order creation, approval, or email sending occurs.</div></div>
  <div class="card"><h2>Regression Health</h2><div class="card-body" id="regressionDashboard"><p class="muted">Loading regression dashboard...</p></div></div>
</div>`, "", "Overview first; detailed checks stay grouped below.");
```

- [ ] **Step 2: Wrap high-use selects**

For selects in the test console and environment-heavy controls, wrap with:

```html
<div class="select-wrap"><select class="cmms-select" ...>...</select></div>
```

Preserve each existing `id`, `onchange`, and option list exactly.

- [ ] **Step 3: Run focused tests**

Run:

```bash
pytest tests/test_progressive_console_ui.py -q
```

Expected: PASS.

### Task 5: Smoke Check the Portal

**Files:**
- Read: `app/ui.py`
- Test: app startup or direct render

- [ ] **Step 1: Run a syntax/import smoke check**

Run:

```bash
python -m py_compile app/ui.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run available UI tests**

Run:

```bash
pytest tests/test_progressive_console_ui.py tests/test_email_intake_ui.py tests/test_safety_reviewer_ui.py -q
```

Expected: PASS.

- [ ] **Step 3: Start the local app if needed and inspect `/ui`**

Run the project’s existing local startup command or FastAPI command used in this repo, then open `/ui`.

Expected: login view renders, navigation is grouped, dashboard has a calmer two-panel summary, and dropdowns have modern rounded styling.
