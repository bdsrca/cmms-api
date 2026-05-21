"""FastAPI-served management portal UI."""

PORTAL_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CMMS LLM Management Portal</title>
  <style>
    :root {
      --azure: #0f62fe;
      --nav: #161616;
      --nav2: #262626;
      --bg: #f4f4f4;
      --panel: #fff;
      --line: #e0e0e0;
      --text: #161616;
      --muted: #525252;
      --danger: #da1e28;
      --ok: #24a148;
      --code: #0b0f19;
      --replicate-line: #e5e7eb;
      --accent: #635bff;
      --accent2: #2563eb;
      --accent-soft: #eef2ff;
      --surface: #ffffff;
      --surface-soft: #fafafa;
      --shadow-sm: 0 1px 2px rgba(16, 24, 40, .05);
      --shadow-md: 0 12px 28px rgba(16, 24, 40, .10);
      --radius: 14px;
      --radius-sm: 10px;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: var(--text); background: var(--bg); }
    .login { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #243642, #0f6cbd); }
    .login-card { width: min(420px, calc(100% - 32px)); background: #fff; border-radius: 2px; box-shadow: 0 18px 42px rgba(0,0,0,.28); padding: 28px; }
    .login-card h1 { margin: 0 0 8px; font-size: 24px; }
    .login-card p { margin: 0 0 22px; color: var(--muted); }
    label { display: block; font-size: 12px; font-weight: 650; margin: 12px 0 6px; color: #374151; }
    input, textarea, select {
      width: 100%; border: 1px solid #8a8886; border-radius: 2px; padding: 8px 10px; font: inherit; background: #fff;
    }
    textarea { min-height: 120px; resize: vertical; }
    button {
      border: 1px solid transparent; border-radius: 2px; padding: 8px 12px; background: var(--azure); color: #fff;
      font: inherit; font-weight: 600; cursor: pointer; min-height: 34px;
    }
    button.secondary { background: #fff; color: var(--text); border-color: #8a8886; }
    button.danger { background: var(--danger); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .app { display: none; min-height: 100vh; grid-template-columns: 260px 1fr; grid-template-rows: 48px 1fr; }
    .top { grid-column: 1 / -1; background: #161616; color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; border-bottom: 3px solid var(--azure); }
    .brand { font-weight: 700; font-size: 16px; }
    .userbar { display: flex; gap: 12px; align-items: center; font-size: 13px; }
    .nav { background: var(--nav); color: #fff; padding: 10px 0; overflow: auto; }
    .nav button { width: 100%; text-align: left; background: transparent; border: 0; border-left: 4px solid transparent; border-radius: 0; padding: 10px 18px; }
    .nav button.active { background: var(--nav2); border-left-color: #69afe5; }
    .nav button.admin-only::after { content: " admin"; color: #c8d1d8; font-size: 11px; float: right; }
    .content { padding: 18px; overflow: auto; }
    .page-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
    .page-title h1 { margin: 0; font-size: 24px; font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 0; }
    .card h2 { margin: 0; padding: 12px 14px; font-size: 16px; border-bottom: 1px solid var(--line); }
    .card-body { padding: 14px; }
    .span-3 { grid-column: span 3; } .span-4 { grid-column: span 4; } .span-5 { grid-column: span 5; } .span-6 { grid-column: span 6; } .span-7 { grid-column: span 7; } .span-8 { grid-column: span 8; } .span-12 { grid-column: span 12; }
    .metric { font-size: 28px; font-weight: 600; margin-bottom: 4px; }
    .muted { color: var(--muted); font-size: 13px; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .stack { display: grid; gap: 10px; }
    pre { margin: 0; background: var(--code); color: #f8fafc; padding: 14px; min-height: 260px; overflow: auto; white-space: pre-wrap; border-radius: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { background: #faf9f8; font-weight: 600; }
    .hidden { display: none !important; }
    .pill { display: inline-block; padding: 2px 7px; border-radius: 999px; background: #e1dfdd; font-size: 12px; }
    .pill.ok { background: #dff6dd; color: var(--ok); }
    .pill.danger { background: #fde7e9; color: var(--danger); }
    .pill.warning { background: #fff4ce; color: #8a6d00; }
    .segmented { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid #8a8886; border-radius: 2px; overflow: hidden; }
    .segmented button { border: 0; border-radius: 0; background: #fff; color: var(--text); }
    .segmented button.active { background: var(--azure); color: #fff; }
    .notice { border-left: 3px solid var(--azure); background: #f3f9fd; padding: 10px; font-size: 13px; }
    .notice.warning { border-left-color: #ffaa44; background: #fff8e1; }
    .voice-panel { border: 1px solid var(--line); background: #faf9f8; padding: 12px; }
    .status-line { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .button-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .email-compose { background: #fbfcfe; }
    .email-compose textarea { min-height: 240px; }
    .email-actions { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .playground { background: #fff; border: 1px solid var(--replicate-line); box-shadow: 0 1px 2px rgba(15,23,42,.04); }
    .playground h2 { border-bottom: 1px solid var(--replicate-line); }
    .playground-header { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 12px 14px; border-bottom: 1px solid var(--replicate-line); }
    .playground-title { font-weight: 700; }
    .playground-subtitle { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .run-surface { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; padding: 14px; }
    .ai-panel { border: 1px solid var(--replicate-line); background: #fff; padding: 12px; }
    .ai-panel-dark { background: #0b0f19; color: #f8fafc; border-color: #0b0f19; }
    .ai-panel-dark pre { min-height: 180px; padding: 0; background: transparent; }
    .result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .readiness { border-left: 3px solid var(--azure); background: #edf5ff; padding: 10px; }
    .readiness.fail { border-left-color: var(--danger); background: #fff1f1; }
    .readiness.warn { border-left-color: #f1c21b; background: #fcf4d6; }
    .code-output { min-height: 520px; }
    .contracts-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
    .detail-form input, .detail-form textarea, .detail-form select { width: 100%; min-width: 0; }
    .detail-form textarea { font-family: Consolas, "Courier New", monospace; }
    .command-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 10px; background: #fff; border: 1px solid var(--line); margin-bottom: 12px; }
    .command-bar select, .command-bar input { width: auto; min-width: 180px; }
    .resource-header { background: #fff; border: 1px solid var(--line); padding: 16px; margin-bottom: 12px; }
    .resource-title { font-size: 22px; font-weight: 600; margin-bottom: 6px; }
    .tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--line); margin-bottom: 12px; }
    .tabs button { background: transparent; color: var(--text); border: 0; border-bottom: 3px solid transparent; border-radius: 0; }
    .tabs button.active { border-bottom-color: var(--azure); color: var(--azure); }
    .blade-layout { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 14px; }
    .blade { background: #fff; border: 1px solid var(--line); min-height: 420px; }
    .blade h2 { margin: 0; padding: 12px 14px; border-bottom: 1px solid var(--line); font-size: 16px; }
    .blade-body { padding: 14px; }
    .clickable-row { cursor: pointer; }
    .clickable-row:hover { background: #f3f9fd; }
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; z-index: 20; }
    .modal { width: min(760px, calc(100% - 32px)); background: #fff; border: 1px solid var(--line); box-shadow: 0 18px 42px rgba(0,0,0,.32); }
    .modal h2 { margin: 0; padding: 14px; border-bottom: 1px solid var(--line); font-size: 18px; }
    .modal-body { padding: 14px; }
    .modal-actions { padding: 12px 14px; border-top: 1px solid var(--line); display: flex; justify-content: flex-end; gap: 8px; }
    .preview-summary { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 12px 0; }
    .preview-summary div { background: #f8f8f8; border: 1px solid var(--line); padding: 10px; }

    /* Modern CMMS control layer: Linear/OpenAI-inspired admin controls with Replicate-style execution panels. */
    body { background: #f7f7f8; letter-spacing: 0; }
    input, textarea, select, .cmms-input, .cmms-select {
      min-height: 38px;
      border: 1px solid #d8dce3;
      border-radius: 10px;
      background: #fff;
      color: #111827;
      padding: 9px 12px;
      outline: none;
      transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
      box-shadow: 0 1px 0 rgba(17, 24, 39, .02);
    }
    textarea { min-height: 132px; line-height: 1.45; }
    input:hover, textarea:hover, select:hover { border-color: #c3c8d2; }
    input:focus, textarea:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 4px rgba(99, 91, 255, .13);
    }
    input:disabled, textarea:disabled, select:disabled {
      background: #f3f4f6;
      color: #6b7280;
      cursor: not-allowed;
    }
    select {
      appearance: none;
      background-image:
        linear-gradient(45deg, transparent 50%, #6b7280 50%),
        linear-gradient(135deg, #6b7280 50%, transparent 50%);
      background-position: calc(100% - 18px) 52%, calc(100% - 13px) 52%;
      background-size: 5px 5px, 5px 5px;
      background-repeat: no-repeat;
      padding-right: 34px;
    }
    input[type="checkbox"] {
      appearance: none;
      width: 18px !important;
      height: 18px;
      min-height: 18px;
      padding: 0;
      border-radius: 5px;
      vertical-align: -4px;
      margin-right: 8px;
      display: inline-grid;
      place-items: center;
    }
    input[type="checkbox"]:checked {
      background: var(--accent);
      border-color: var(--accent);
    }
    input[type="checkbox"]:checked::after {
      content: "";
      width: 9px;
      height: 5px;
      border: 2px solid #fff;
      border-top: 0;
      border-right: 0;
      transform: rotate(-45deg);
      margin-top: -2px;
    }
    button, .cmms-btn {
      min-height: 38px;
      border-radius: 10px;
      border: 1px solid transparent;
      padding: 8px 14px;
      background: linear-gradient(180deg, #6d66ff, #554cf2);
      color: #fff;
      box-shadow: 0 1px 2px rgba(17, 24, 39, .08);
      transition: transform .12s ease, box-shadow .16s ease, background .16s ease, border-color .16s ease;
    }
    button:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(85, 76, 242, .18); }
    button:active:not(:disabled) { transform: translateY(0); box-shadow: 0 1px 2px rgba(17, 24, 39, .08); }
    button.secondary, .cmms-btn.secondary {
      background: #fff;
      color: #111827;
      border-color: #d8dce3;
      box-shadow: var(--shadow-sm);
    }
    button.secondary:hover:not(:disabled) { border-color: #b9c0cc; box-shadow: 0 6px 14px rgba(17, 24, 39, .08); }
    button.danger, .cmms-btn.danger { background: #dc2626; color: #fff; }
    button:disabled { background: #eef0f4; color: #9ca3af; border-color: #e5e7eb; box-shadow: none; transform: none; }
    .login { background: radial-gradient(circle at 30% 20%, #eef2ff, transparent 32%), linear-gradient(135deg, #fbfbfc, #eef2ff); }
    .login-card {
      border-radius: 20px;
      border: 1px solid rgba(229, 231, 235, .9);
      box-shadow: var(--shadow-md);
      padding: 32px;
    }
    .login-card h1 { font-size: 26px; letter-spacing: -.01em; }
    .app { grid-template-columns: 190px 1fr; grid-template-rows: 52px 1fr; }
    .top {
      background: rgba(255, 255, 255, .88);
      color: #111827;
      border-bottom: 1px solid #e5e7eb;
      backdrop-filter: blur(12px);
    }
    .brand { font-size: 15px; letter-spacing: -.01em; }
    .userbar button.secondary { min-height: 32px; padding: 6px 11px; }
    .nav { background: #fff; color: #111827; border-right: 1px solid #e5e7eb; padding: 12px 8px; }
    .nav button {
      color: #374151;
      border: 0;
      border-radius: 10px;
      padding: 9px 11px;
      margin: 2px 0;
      display: flex;
      align-items: center;
      gap: 9px;
      font-weight: 620;
      font-size: 13px;
    }
    .nav button:hover { background: #f4f4f5; transform: none; box-shadow: none; }
    .nav button.active { background: var(--accent-soft); color: #3730a3; border-left-color: transparent; }
    .nav button.admin-only::after {
      content: "●";
      color: #ef4444;
      font-size: 11px;
      margin-left: auto;
      float: none;
    }
    .cmms-nav-icon { width: 18px; text-align: center; opacity: .82; }
    .content { padding: 22px; }
    .page-title h1 { font-size: 26px; letter-spacing: -.025em; }
    .card, .cmms-card, .playground, .blade, .modal, .resource-header {
      border-radius: var(--radius);
      border-color: #e5e7eb;
      box-shadow: var(--shadow-sm);
      overflow: hidden;
    }
    .card h2, .blade h2, .modal h2 {
      font-size: 15px;
      background: #fff;
      border-bottom-color: #eef0f3;
    }
    .ai-panel, .voice-panel, .readiness {
      border-radius: 14px;
      border-color: #e5e7eb;
      box-shadow: var(--shadow-sm);
    }
    .ai-panel-dark, .cmms-code-panel {
      border-radius: 14px;
      background: #0f172a;
      border-color: #111827;
      box-shadow: 0 12px 28px rgba(15, 23, 42, .16);
    }
    pre { border-radius: 12px; font-size: 12px; line-height: 1.5; }
    table { border-collapse: separate; border-spacing: 0; }
    th {
      background: #f9fafb;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: .02em;
      font-size: 11px;
      border-bottom: 1px solid #e5e7eb;
    }
    td { border-bottom-color: #eef0f3; }
    tr:hover td { background: #fafafa; }
    .pill, .cmms-badge {
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 11px;
      font-weight: 650;
      background: #f3f4f6;
      color: #4b5563;
    }
    .pill.ok { background: #ecfdf3; color: #027a48; }
    .pill.danger { background: #fef2f2; color: #b42318; }
    .pill.warning { background: #fffaeb; color: #b54708; }
    .segmented, .cmms-segmented {
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 3px;
      gap: 3px;
    }
    .segmented button {
      min-height: 32px;
      border-radius: 9px;
      background: transparent;
      color: #4b5563;
      box-shadow: none;
    }
    .segmented button.active {
      background: #fff;
      color: #111827;
      box-shadow: var(--shadow-sm);
    }
    .command-bar, .cmms-command-bar {
      border-radius: 14px;
      border-color: #e5e7eb;
      box-shadow: var(--shadow-sm);
      padding: 12px;
    }
    .command-bar select, .command-bar input { min-height: 36px; }
    .modal-backdrop { background: rgba(15, 23, 42, .35); backdrop-filter: blur(4px); }
    .modal { border-radius: 18px; box-shadow: var(--shadow-md); }
    .modal-actions { background: #fafafa; }
    .preview-summary div { border-radius: 12px; background: #fff; border-color: #e5e7eb; }
    @media (max-width: 1200px) { .contracts-layout { grid-template-columns: 1fr; } }
    @media (max-width: 900px) { .app { grid-template-columns: 1fr; } .nav { display: flex; overflow-x: auto; } .nav button { min-width: 180px; } .span-3,.span-4,.span-5,.span-6,.span-7,.span-8 { grid-column: span 12; } .result-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div id="loginView" class="login">
    <div class="login-card">
      <h1>CMMS LLM Portal</h1>
      <p>Sign in to manage environments, API keys, reports, and testing.</p>
      <label>Username</label><input id="loginUser" value="admin">
      <label>Password</label><input id="loginPass" type="password" placeholder="Enter admin password">
      <div class="row" style="margin-top:18px"><button onclick="login()">Sign in</button><span id="loginMsg" class="muted"></span></div>
    </div>
  </div>
  <div id="appView" class="app">
    <header class="top">
      <div class="brand">CMMS LLM Management Portal</div>
      <div class="userbar"><span id="healthText">Checking...</span><span id="userText"></span><button class="secondary" onclick="logout()">Logout</button></div>
    </header>
    <nav class="nav" id="nav"></nav>
    <main class="content">
      <div class="page-title"><h1 id="pageTitle">Dashboard</h1><div id="pageActions"></div></div>
      <div id="page"></div>
    </main>
  </div>
  <script>
    const state = {
      me: null, page: "dashboard", envs: [], keys: [], output: {}, selectedEnv: "DEFAULT", defaultApiKey: "my-secret-key",
      envTab: "codes", selectedCategory: "buildings", selectedCode: null, codeData: null, validationRules: [],
      inputMode: "text", recognition: null, voiceSupported: null, voiceBaseTranscript: "", voiceFinalTranscript: "",
      voiceStopping: false, voiceStatus: "Idle", voiceSilenceTimer: null, outputs: {},
      lastTestResponse: null, lastTestInput: null, selectedTestCaseId: null
    };
    const menu = [
      ["dashboard","Dashboard",false,"▦"],["test","Test Console",false,"▶"],["email","Email Intake",false,"✉"],["builder","API Builder",false,"⌘"],["testCases","Test Cases",true,"✓"],["testSuites","Test Suites",true,"✓"],
      ["environments","Environments",true,"◇"],["contracts","Output Contracts",true,"▣"],["prompts","Prompt Versions",true,"✎"],["keys","API Keys",true,"◆"],
      ["users","Users",true,"◉"],["logs","Logs",false,"☰"],["reports","Reports",false,"↗"],["kb","Knowledge Base",false,"◌"],
      ["remote","Remote Access",true,"⇄"],["system","System",true,"⚙"]
    ];
    const codeCategories = [
      ["buildings","Buildings"],["rooms","Rooms"],["priorities","Priorities"],["work_order_types","Work order types"],
      ["assign_to","Assign to"],["issue_to_employee_number","Issue to employee #"],["job_type","Job type"],["custom:future","Custom future"]
    ];
    const $ = (id) => document.getElementById(id);
    async function api(path, opts = {}) {
      const res = await fetch(path, { credentials: "same-origin", ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
      if (!res.ok) throw Object.assign(new Error(data.detail || "Request failed"), { data, status: res.status });
      return data;
    }
    async function login() {
      try {
        await api("/auth/login", { method: "POST", body: JSON.stringify({ username: $("loginUser").value, password: $("loginPass").value }) });
        await boot();
      } catch (e) { $("loginMsg").textContent = e.message; }
    }
    async function logout() { await api("/auth/logout", { method: "POST" }).catch(() => {}); location.reload(); }
    async function boot() {
      try {
        state.me = await api("/api/me");
        $("loginView").style.display = "none"; $("appView").style.display = "grid";
        $("userText").textContent = `${state.me.username} (${state.me.role})`;
        renderNav(); await refreshBase(); show("dashboard");
      } catch { $("loginView").style.display = "grid"; $("appView").style.display = "none"; }
    }
    async function refreshBase() {
      state.envs = await api("/api/environments").catch(() => []);
      state.keys = state.me?.role === "admin" ? await api("/api/admin/api-keys").catch(() => []) : [];
      const keyInfo = await api("/api/default-api-key").catch(() => null);
      if (keyInfo?.api_key) state.defaultApiKey = keyInfo.api_key;
      const health = await api("/health").catch(() => null);
      $("healthText").textContent = health ? "Local API online" : "API offline";
    }
    function renderNav() {
      $("nav").innerHTML = menu.map(([id,label,admin,icon]) => {
        if (admin && state.me.role !== "admin") return "";
        return `<button class="${state.page===id?'active':''} ${admin?'admin-only':''}" onclick="show('${id}')"><span class="cmms-nav-icon">${icon}</span><span>${label}</span></button>`;
      }).join("");
    }
    function pageShell(title, html) { $("pageTitle").textContent = title; $("pageActions").innerHTML = ""; $("page").innerHTML = html; renderNav(); }
    function envOptions() { return state.envs.map(e => `<option value="${e.environment_code}">${e.environment_code} - ${e.name}</option>`).join(""); }
    function show(id) {
      state.page = id; renderNav();
      const handlers = { dashboard, test, email: emailIntake, builder, testCases, testSuites, environments, contracts, prompts, keys, users, logs, reports, kb, remote, system };
      handlers[id]();
    }
    async function dashboard() {
      pageShell("Dashboard", `<div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${state.envs.length}</div><div class="muted">Environments</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${state.keys.length}</div><div class="muted">API keys</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${state.me.role}</div><div class="muted">Current role</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">Local</div><div class="muted">Model runtime</div></div></div>
        <div class="card span-12"><h2>Safety posture</h2><div class="card-body">Advisory mode only. No CMMS write-back, work order creation, approval, or email sending occurs.</div></div>
        <div class="card span-12"><h2>Regression Health</h2><div class="card-body" id="regressionDashboard"><p class="muted">Loading regression dashboard...</p></div></div>
      </div>`);
      const data = await api("/api/admin/regression-dashboard").catch(e => ({ error: e.message }));
      renderRegressionDashboard(data);
    }

    function renderRegressionDashboard(data) {
      if (!$("regressionDashboard")) return;
      if (data.error) { $("regressionDashboard").innerHTML = `<span class="pill danger">Dashboard unavailable</span><p>${escapeHtml(data.error)}</p>`; return; }
      const readiness = data.required_suite_readiness || {};
      const workflow = data.workflow_summary || {};
      $("regressionDashboard").innerHTML = `<div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.passed ?? 0}/${readiness.total ?? 0}</div><div class="muted">Required suites passed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.failed ?? 0}</div><div class="muted">Required suites failed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.not_run ?? 0}</div><div class="muted">Required suites not run</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${workflow.failed ?? 0}</div><div class="muted">Recent workflow failures</div></div></div>
        <div class="card span-12"><h2>Required Suite Readiness</h2><div class="card-body">${renderRequiredSuiteReadiness(readiness.items || [])}</div></div>
        <div class="card span-12"><h2>Latest Suite Runs</h2><div class="card-body">${renderDashboardSuiteRuns(data.latest_suite_runs || [])}</div></div>
        <div class="card span-6"><h2>Recent Prompt Comparisons</h2><div class="card-body">${renderDashboardComparisons(data.recent_prompt_comparisons || [])}</div></div>
        <div class="card span-6"><h2>Recent Promotions</h2><div class="card-body">${renderDashboardPromotions(data.recent_promotions || [])}</div></div>
        <div class="card span-4"><h2>Workflow Summary</h2><div class="card-body">${renderWorkflowSummary(workflow)}</div></div>
        <div class="card span-4"><h2>Top Failing Fields</h2><div class="card-body">${renderFailingFields(data.top_failing_fields || [])}</div></div>
        <div class="card span-4"><h2>Recent Validation Failures</h2><div class="card-body">${renderValidationFailures(data.recent_validation_failures || [])}</div></div>
      </div>`;
    }

    function statusPill(status) {
      return `<span class="pill ${status === "passed" || status === "completed" ? "ok" : status === "warning" || status === "completed_with_warnings" || status === "not_run" ? "warning" : "danger"}">${escapeHtml(status || "")}</span>`;
    }

    function renderRequiredSuiteReadiness(rows) {
      if (!rows.length) return '<p class="muted">No required suites configured.</p>';
      return `<table><thead><tr><th>Suite</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Pass Rate</th><th>Status</th><th>Last Run</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.latest_prompt_version || "")}</td><td>${r.pass_rate ?? ""}</td><td>${statusPill(r.status)}</td><td>${escapeHtml(r.last_run_at || "")}</td><td>${r.latest_suite_run_id ? `<button class="secondary" onclick="viewTestSuiteRun('${escapeAttr(r.latest_suite_run_id)}')">View Suite Run</button>` : ""}</td></tr>`).join("")}</tbody></table>`;
    }

    function renderDashboardSuiteRuns(rows) {
      if (!rows.length) return '<p class="muted">No suite runs yet.</p>';
      return `<table><thead><tr><th>Run</th><th>Suite</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Status</th><th>Pass Rate</th><th>Started</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.suite_run_id)}</td><td>${escapeHtml(r.suite_name || "")}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.prompt_version || "")}</td><td>${statusPill(r.status)}</td><td>${r.pass_rate ?? ""}</td><td>${escapeHtml(r.started_at || "")}</td><td><button class="secondary" onclick="viewTestSuiteRun('${escapeAttr(r.suite_run_id)}')">View</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderDashboardComparisons(rows) {
      if (!rows.length) return '<p class="muted">No prompt comparisons yet.</p>';
      return `<table><thead><tr><th>Comparison</th><th>Endpoint</th><th>Improved</th><th>Regressed</th><th>Error</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.comparison_id)}</td><td>${escapeHtml(r.endpoint)}</td><td>${r.improved}</td><td>${r.regressed}</td><td>${r.error}</td><td><button class="secondary" onclick="show('prompts'); setTimeout(()=>viewPromptComparison('${escapeAttr(r.comparison_id)}'), 100)">View</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderDashboardPromotions(rows) {
      if (!rows.length) return '<p class="muted">No prompt promotions yet.</p>';
      return `<table><thead><tr><th>Promotion</th><th>Endpoint</th><th>Promoted</th><th>Gate</th><th>Override</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.promotion_id)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.promoted_prompt || "")}</td><td>${statusPill(r.gate_status)}</td><td>${r.override_used ? "Yes" : "No"}</td><td><button class="secondary" onclick="viewPromptPromotion('${escapeAttr(r.promotion_id)}')">View</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderWorkflowSummary(w) {
      return `<div class="stack"><div>Total: <strong>${w.total ?? 0}</strong></div><div>Completed: <strong>${w.completed ?? 0}</strong></div><div>Warnings: <strong>${w.completed_with_warnings ?? 0}</strong></div><div>Failed: <strong>${w.failed ?? 0}</strong></div><div>Avg duration: <strong>${w.avg_duration_ms ?? 0} ms</strong></div></div>`;
    }

    function renderFailingFields(rows) {
      if (!rows.length) return '<p class="muted">No failing fields found.</p>';
      return `<table><thead><tr><th>Field</th><th>Count</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.field)}</td><td>${r.count}</td></tr>`).join("")}</tbody></table>`;
    }

    function renderValidationFailures(rows) {
      if (!rows.length) return '<p class="muted">No recent validation failures.</p>';
      return `<table><thead><tr><th>When</th><th>Source</th><th>Field</th><th>Message</th></tr></thead><tbody>${rows.map(r => `<tr><td>${escapeHtml(r.timestamp || "")}</td><td>${escapeHtml(r.source_type)}</td><td>${escapeHtml(r.field || "")}</td><td>${escapeHtml(r.message || "")}</td></tr>`).join("")}</tbody></table>`;
    }
    function test() {
      pageShell("Test Console", `<div class="grid">
        <div class="card playground span-4"><div class="playground-header"><div><div class="playground-title">Run console</div><div class="playground-subtitle">Text and voice.</div></div><span class="pill">API</span></div><div class="card-body stack">
          <label>API key</label><input id="tKey" type="password" value="${escapeAttr(state.defaultApiKey)}">
          <label>Mode</label><select id="tEndpoint" onchange="renderTestModeHelp()"><option value="cmms-intake">CMMS Intake</option><option value="cmms-assistant">CMMS Assistant Chat</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select>
          <label>Environment</label><select id="tEnv">${envOptions()}</select>
          <div id="testModeHelp" class="notice"></div>
          <div id="testInputPanel"></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Response</div><div class="playground-subtitle" id="inputSourceLabel">Input source: none</div></div><span id="runStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="tReadiness" class="readiness"><strong>Work order readiness</strong><div class="muted">Run CMMS Intake to evaluate whether enough validated information exists for a human-controlled workflow.</div></div>
            <div class="ai-panel"><h3>Workflow Trace</h3><div id="tTrace"><span class="muted">Run CMMS Intake to see trace steps.</span></div></div>
            <div class="result-grid">
              <div class="ai-panel"><h3>Contract Validation</h3><div id="tContract"><span class="muted">Run a request to see contract validation.</span></div></div>
              <div class="ai-panel"><h3>Environment Validation</h3><div id="tValidation"><span class="muted">Run a request to see environment validation.</span></div></div>
            </div>
            <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Extracted JSON</strong>${outputToolbar("tOut")}</div><pre id="tOut">{}</pre></div>
          </div>
        </div>
      </div>`);
      renderTestInputPanel();
      renderTestModeHelp();
    }
    function emailIntake() {
      pageShell("Email Intake", `<div class="grid">
        <div class="card playground span-5"><div class="playground-header"><div><div class="playground-title">Email</div><div class="playground-subtitle">Paste or import.</div></div><span class="pill">email_api</span></div><div class="card-body stack">
          <label>API key</label><input id="eKey" type="password" value="${escapeAttr(state.defaultApiKey)}">
          <label>Environment</label><select id="eEnv">${envOptions()}</select>
          <div class="ai-panel stack email-compose">
            <label>From</label><input id="emailFrom" placeholder="tenant@example.com">
            <label>To</label><input id="emailTo" placeholder="maintenance@example.com">
            <label>Submitted by</label><input id="emailSubmittedBy" placeholder="John Smith">
            <label>Phone</label><input id="emailPhone" placeholder="416-555-0101">
            <label>Requested due</label><input id="emailDue" placeholder="2026-05-24T17:00:00Z">
            <label>Location</label><input id="emailLocationRaw" placeholder="ARC room 205">
            <div class="row"><div style="flex:1"><label>Building</label><input id="emailBuilding" placeholder="ARC"></div><div style="flex:1"><label>Room</label><input id="emailRoom" placeholder="205"></div></div>
            <label>Subject</label><input id="emailSubject" placeholder="Leak in ARC 205">
            <label>Body</label><textarea id="emailBody" placeholder="Paste email body"></textarea>
            <input id="emailImportFile" type="file" accept=".eml,.txt,message/rfc822,text/plain" style="display:none" onchange="handleEmailImport(event)">
            <div class="button-grid email-actions"><button class="secondary" onclick="$('emailImportFile').click()">Import</button><button class="secondary" onclick="clearEmailIntake()">Clear</button><button id="eRunBtn" onclick="runEmailIntake()">Run Email</button></div>
          </div>
        </div></div>
        <div class="card playground span-7"><div class="playground-header"><div><div class="playground-title">Response</div><div class="playground-subtitle" id="inputSourceLabel">Input source: email API</div></div><span id="runStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="tReadiness" class="readiness"><strong>Work order readiness</strong><div class="muted">Run Email to evaluate the request.</div></div>
            <div class="ai-panel"><h3>Workflow Trace</h3><div id="tTrace"><span class="muted">No run yet.</span></div></div>
            <div class="result-grid">
              <div class="ai-panel"><h3>Contract Validation</h3><div id="tContract"><span class="muted">No run yet.</span></div></div>
              <div class="ai-panel"><h3>Environment Validation</h3><div id="tValidation"><span class="muted">No run yet.</span></div></div>
            </div>
            <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Extracted JSON</strong>${outputToolbar("tOut")}</div><pre id="tOut">{}</pre></div>
          </div>
        </div>
      </div>`);
    }
    function renderTestInputPanel() {
      if (!$("testInputPanel")) return;
      const supported = getSpeechRecognitionCtor();
      state.voiceSupported = Boolean(supported);
      $("testInputPanel").innerHTML = `<div class="ai-panel stack">
          <label>Content</label>
          <textarea id="tText">The air conditioner in ARC room 205 is making loud noise and the room is too warm.</textarea>
          <div class="button-grid"><button id="runTestBtn" onclick="runTest('text')">Run Text</button><button class="secondary" onclick="clearVoiceTranscript()">Clear</button><button class="secondary" onclick="openSaveCurrentTestCase()">Save as Test Case</button><button class="secondary" onclick="runMatchingTestCase()">Run Matching Test</button></div>
        </div>
        <div class="voice-panel stack">
          <div class="status-line"><strong>Metadata</strong><span class="pill">optional</span></div>
          <label>Submitted by</label><input id="testSubmittedBy" placeholder="John Smith">
          <label>Email</label><input id="testSubmittedEmail" placeholder="john@example.com">
          <label>Phone</label><input id="testSubmittedPhone" placeholder="416-555-0101">
          <label>Requested due</label><input id="testDue" placeholder="2026-05-24T17:00:00Z">
          <label>Location</label><input id="testLocationRaw" placeholder="ARC room 205">
          <div class="row"><div style="flex:1"><label>Building</label><input id="testBuilding" placeholder="ARC"></div><div style="flex:1"><label>Room</label><input id="testRoom" placeholder="205"></div></div>
        </div>
        <div class="voice-panel stack">
          <div class="status-line"><strong>Speech provider: Browser Speech Recognition</strong><span id="voiceStatus" class="pill">${escapeHtml(state.voiceStatus || "Idle")}</span></div>
          ${supported ? "" : '<div class="notice warning">Speech recognition is not available in this browser. Use Chrome, Edge, or Safari, or continue with text input.</div>'}
          <label>Language</label><select id="voiceLang" onchange="updateVoiceLanguage()">
            <option value="en-CA">English - Canada</option>
            <option value="en-US">English - US</option>
            <option value="zh-CN">Chinese - Simplified Mandarin</option>
            <option value="zh-TW">Chinese - Traditional Mandarin</option>
            <option value="fr-CA">French - Canada</option>
            <option value="es-ES">Spanish - Spain</option>
            <option value="ja-JP">Japanese</option>
            <option value="ko-KR">Korean</option>
          </select>
          <div class="button-grid">
            <button onclick="startVoiceRecognition()" ${supported ? "" : "disabled"}>Start Listening</button>
            <button class="secondary" onclick="stopVoiceRecognition()" ${supported ? "" : "disabled"}>Stop</button>
          </div>
          <div class="muted">Listening stops automatically after 5 seconds without detected speech.</div>
          <div id="voiceMessage" class="muted">Speech recognition is handled by the browser. This app does not store audio. Review the transcript before sending.</div>
        </div>`;
    }
    async function renderTestModeHelp() {
      if (!$("testModeHelp")) return;
      const ep = $("tEndpoint")?.value || "cmms-intake";
      const copy = {
        "cmms-intake": "Controlled extraction workflow: contract validation, environment validation, readiness, and advisory drafts.",
        "cmms-assistant": "Controlled CMMS assistant chat. It can discuss intake, validation, API usage, and drafts, but cannot create work orders or write to CMMS.",
        "extract-work-order-fields": "Field extraction only. Useful for debugging request type, building, room, priority, and missing fields.",
        "summarize-work-order": "One-sentence work request summary. No readiness validation."
      };
      $("testModeHelp").textContent = copy[ep] || copy["cmms-intake"];
      const promptInfo = await api(`/api/prompt-versions/active/${ep}`).catch(() => null);
      if (promptInfo) {
        $("testModeHelp").innerHTML = `${escapeHtml(copy[ep] || copy["cmms-intake"])}<div class="muted" style="margin-top:6px">Prompt Version: <strong>${escapeHtml(promptInfo.endpoint)} ${escapeHtml(promptInfo.version)}</strong> · temperature ${promptInfo.temperature}</div>`;
      }
    }
    function getSpeechRecognitionCtor() { return window.SpeechRecognition || window.webkitSpeechRecognition; }
    function updateVoiceLanguage() {
      if (state.recognition && $("voiceLang")) state.recognition.lang = $("voiceLang").value;
    }
    function setVoiceStatus(status, message) {
      state.voiceStatus = status;
      if ($("voiceStatus")) {
        $("voiceStatus").textContent = status;
        $("voiceStatus").className = `pill ${status === "Error" ? "danger" : status === "Listening" ? "ok" : status === "Processing" ? "warning" : ""}`;
      }
      if (message && $("voiceMessage")) $("voiceMessage").textContent = message;
    }
    function transcriptValue() {
      return ($("tText")?.value || "").trim();
    }
    function writeTranscript(interimText = "") {
      const parts = [state.voiceBaseTranscript, state.voiceFinalTranscript, interimText].map(v => (v || "").trim()).filter(Boolean);
      if ($("tText")) $("tText").value = parts.join(" ");
    }
    function startVoiceRecognition() {
      const SpeechRecognitionCtor = getSpeechRecognitionCtor();
      if (!SpeechRecognitionCtor) {
        setVoiceStatus("Error", "Speech recognition is not available in this browser. Use Chrome, Edge, or Safari, or continue with text input.");
        return;
      }
      if (state.recognition) {
        setVoiceStatus("Listening", "Speech recognition is already running.");
        return;
      }
      state.voiceBaseTranscript = transcriptValue();
      state.voiceFinalTranscript = "";
      state.voiceStopping = false;
      const recognition = new SpeechRecognitionCtor();
      state.recognition = recognition;
      recognition.lang = $("voiceLang")?.value || "en-CA";
      recognition.interimResults = true;
      try { recognition.continuous = true; } catch {}
      recognition.onstart = () => { setVoiceStatus("Listening", "Listening. The transcript will appear in the text box."); resetVoiceSilenceTimer(); };
      recognition.onerror = (event) => {
        const messages = {
          "not-allowed": "Microphone permission was denied. Allow microphone access or continue with text input.",
          "service-not-allowed": "Speech recognition service is blocked in this browser.",
          "no-speech": "No speech was detected. Try again or type the request.",
          "audio-capture": "No microphone was found or it could not be used.",
          "network": "Speech recognition network error. Try again or continue with text input."
        };
        setVoiceStatus("Error", messages[event.error] || `Speech recognition error: ${event.error || "unknown"}.`);
      };
      recognition.onresult = (event) => {
        setVoiceStatus("Processing");
        let finalChunk = "";
        let interimChunk = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const text = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalChunk += `${text} `;
          else interimChunk += text;
        }
        if (finalChunk.trim()) state.voiceFinalTranscript = `${state.voiceFinalTranscript} ${finalChunk}`.trim();
        writeTranscript(interimChunk);
        resetVoiceSilenceTimer();
        setVoiceStatus("Listening");
      };
      recognition.onend = () => {
        clearVoiceSilenceTimer();
        state.recognition = null;
        const endedWithError = state.voiceStatus === "Error";
        if (!endedWithError) setVoiceStatus("Idle", state.voiceStopping ? "Listening stopped. Review the transcript before sending." : "Speech recognition ended. Review the transcript before sending.");
      };
      try { recognition.start(); } catch (e) { setVoiceStatus("Error", e.message || "Could not start speech recognition."); }
    }
    function stopVoiceRecognition() {
      state.voiceStopping = true;
      if (state.recognition) {
        setVoiceStatus("Processing", "Stopping speech recognition...");
        try { state.recognition.stop(); } catch { state.recognition = null; setVoiceStatus("Idle"); }
      } else {
        setVoiceStatus("Idle", "Speech recognition is not running.");
      }
    }

    function clearVoiceSilenceTimer() {
      if (state.voiceSilenceTimer) {
        clearTimeout(state.voiceSilenceTimer);
        state.voiceSilenceTimer = null;
      }
    }

    function resetVoiceSilenceTimer() {
      clearVoiceSilenceTimer();
      state.voiceSilenceTimer = setTimeout(() => {
        if (state.recognition) {
          state.voiceStopping = true;
          setVoiceStatus("Processing", "Stopped automatically after 5 seconds without detected speech.");
          try { state.recognition.stop(); } catch {}
        }
      }, 5000);
    }
    function clearVoiceTranscript() {
      state.voiceBaseTranscript = "";
      state.voiceFinalTranscript = "";
      if ($("tText")) $("tText").value = "";
      clearTestMetadata();
      if ($("emailFrom")) $("emailFrom").value = "";
      if ($("emailTo")) $("emailTo").value = "";
      if ($("emailSubmittedBy")) $("emailSubmittedBy").value = "";
      if ($("emailPhone")) $("emailPhone").value = "";
      if ($("emailDue")) $("emailDue").value = "";
      if ($("emailLocationRaw")) $("emailLocationRaw").value = "";
      if ($("emailBuilding")) $("emailBuilding").value = "";
      if ($("emailRoom")) $("emailRoom").value = "";
      if ($("emailSubject")) $("emailSubject").value = "";
      if ($("emailBody")) $("emailBody").value = "";
      setVoiceStatus("Idle", "Transcript cleared.");
    }
    function buildEmailIntakeContent() {
      const from = ($("emailFrom")?.value || "").trim();
      const to = ($("emailTo")?.value || "").trim();
      const subject = ($("emailSubject")?.value || "").trim();
      const body = ($("emailBody")?.value || "").trim() || transcriptValue();
      const parts = ["Email intake"];
      if (from) parts.push(`From: ${from}`);
      if (to) parts.push(`To: ${to}`);
      if (subject) parts.push(`Subject: ${subject}`);
      parts.push("", "Body:", body);
      return parts.join("\n").trim();
    }
    function clearTestMetadata() {
      for (const id of ["testSubmittedBy", "testSubmittedEmail", "testSubmittedPhone", "testDue", "testLocationRaw", "testBuilding", "testRoom"]) {
        if ($(id)) $(id).value = "";
      }
    }
    function buildTestIntakeMetadata(source) {
      const submission = {
        submitted_by: ($("testSubmittedBy")?.value || "").trim() || null,
        submitted_email: ($("testSubmittedEmail")?.value || "").trim() || null,
        submitted_phone: ($("testSubmittedPhone")?.value || "").trim() || null,
        submitted_method: source === "voice_transcript" ? "voice_transcript" : "manual"
      };
      const request = {
        requested_due_at: ($("testDue")?.value || "").trim() || null,
        location: {
          raw: ($("testLocationRaw")?.value || "").trim() || null,
          building: ($("testBuilding")?.value || "").trim() || null,
          room: ($("testRoom")?.value || "").trim() || null,
          area: null
        }
      };
      return { submission, request };
    }
    function copyEmailToText() {
      if ($("tText")) $("tText").value = buildEmailIntakeContent();
    }
    function clearEmailIntake() {
      if ($("emailFrom")) $("emailFrom").value = "";
      if ($("emailTo")) $("emailTo").value = "";
      if ($("emailSubmittedBy")) $("emailSubmittedBy").value = "";
      if ($("emailPhone")) $("emailPhone").value = "";
      if ($("emailDue")) $("emailDue").value = "";
      if ($("emailLocationRaw")) $("emailLocationRaw").value = "";
      if ($("emailBuilding")) $("emailBuilding").value = "";
      if ($("emailRoom")) $("emailRoom").value = "";
      if ($("emailSubject")) $("emailSubject").value = "";
      if ($("emailBody")) $("emailBody").value = "";
      setConsoleOutput("tOut", {});
      if ($("runStatus")) $("runStatus").textContent = "Ready";
    }
    function parseImportedEmail(raw) {
      const normalized = raw.replace(/\r\n/g, "\n");
      const splitAt = normalized.indexOf("\n\n");
      const headerText = splitAt >= 0 ? normalized.slice(0, splitAt) : "";
      const body = splitAt >= 0 ? normalized.slice(splitAt + 2).trim() : normalized.trim();
      const unfolded = headerText.replace(/\n[ \t]+/g, " ");
      const header = (name) => {
        const match = unfolded.match(new RegExp(`^${name}:\\s*(.+)$`, "im"));
        return match ? match[1].trim() : "";
      };
      return { from: header("From"), to: header("To"), subject: header("Subject"), body };
    }
    async function handleEmailImport(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const raw = await file.text();
      const parsed = parseImportedEmail(raw);
      if ($("emailFrom") && parsed.from) $("emailFrom").value = parsed.from;
      if ($("emailTo") && parsed.to) $("emailTo").value = parsed.to;
      if ($("emailSubject") && parsed.subject) $("emailSubject").value = parsed.subject;
      if ($("emailBody")) $("emailBody").value = parsed.body || raw;
      copyEmailToText();
      event.target.value = "";
    }
    async function runEmailIntake() {
      const payload = {
        from_email: ($("emailFrom")?.value || "").trim(),
        to_email: ($("emailTo")?.value || "").trim(),
        submitted_by: ($("emailSubmittedBy")?.value || "").trim() || null,
        submitted_phone: ($("emailPhone")?.value || "").trim() || null,
        requested_due_at: ($("emailDue")?.value || "").trim() || null,
        location: {
          raw: ($("emailLocationRaw")?.value || "").trim() || null,
          building: ($("emailBuilding")?.value || "").trim() || null,
          room: ($("emailRoom")?.value || "").trim() || null,
          area: null
        },
        subject: ($("emailSubject")?.value || "").trim(),
        body: ($("emailBody")?.value || "").trim(),
        environment_code: $("eEnv").value
      };
      if (!payload.from_email || !payload.to_email || !payload.subject || !payload.body) {
        setConsoleOutput("tOut", { error: "Email content is required." });
        if ($("runStatus")) $("runStatus").textContent = "Error";
        return;
      }
      try {
        setRunLoading(true);
        const data = await api("/api/ai/intake/email", { method: "POST", headers: { "x-api-key": $("eKey").value }, body: JSON.stringify(payload) });
        if ($("inputSourceLabel")) $("inputSourceLabel").textContent = "Input source: email API";
        if ($("runStatus")) $("runStatus").textContent = "Complete";
        setConsoleOutput("tOut", data);
        state.lastTestResponse = data;
        state.lastTestInput = { endpoint: "intake/email", environment_code: $("eEnv").value, text: buildEmailIntakeContent(), source: "email_api" };
        renderContractValidation(data.contract);
        renderTestValidation(data.ai_validation);
        renderReadiness(data);
        renderWorkflowTraceFromResponse(data, "tTrace");
      } catch (e) {
        if ($("runStatus")) $("runStatus").textContent = "Error";
        setConsoleOutput("tOut", e.data || { error: e.message });
      } finally {
        setRunLoading(false);
      }
    }
    function setVoiceSample(lang) {
      const samples = {
        en: "There is a water leak in ARC room 205. It looks urgent.",
        zh: "ARC 205 \u623f\u95f4\u6709\u6f0f\u6c34\u95ee\u9898\uff0c\u6bd4\u8f83\u7d27\u6025\u3002",
        fr: "Il y a une fuite d'eau dans la salle ARC 205. C'est urgent."
      };
      if ($("tText")) $("tText").value = samples[lang] || samples.en;
      state.voiceBaseTranscript = transcriptValue();
      state.voiceFinalTranscript = "";
      setVoiceStatus("Idle", "Sample transcript loaded. Review it before sending.");
    }
    async function runTest(sourceOverride) {
      const ep = $("tEndpoint").value;
      const source = sourceOverride || "text";
      const text = source === "email_paste" ? buildEmailIntakeContent() : transcriptValue();
      if (!text) {
        const message = source === "voice_transcript" ? "Transcript is empty. Speak, type, or choose a sample before sending." : source === "email_paste" ? "Email content is required. Paste or import an email before sending." : "Text is required.";
        if (source === "voice_transcript") setVoiceStatus("Error", message);
        setConsoleOutput("tOut", { error: message });
        return;
      }
      const body = { text, environment_code: $("tEnv").value };
      if (source !== "text") body.source = source;
      if (ep === "cmms-intake") {
        const metadata = buildTestIntakeMetadata(source);
        body.submission = metadata.submission;
        body.request = metadata.request;
      }
      try {
        setRunLoading(true);
        const data = await api(`/api/ai/${ep}`, { method: "POST", headers: { "x-api-key": $("tKey").value }, body: JSON.stringify(body) });
        const sourceLabels = { text: "text", voice_transcript: "voice transcript", email_paste: "email paste" };
        if ($("inputSourceLabel")) $("inputSourceLabel").textContent = `Input source: ${sourceLabels[source] || source}`;
        if ($("runStatus")) $("runStatus").textContent = "Complete";
        setConsoleOutput("tOut", data);
        state.lastTestResponse = data;
        state.lastTestInput = { endpoint: ep, environment_code: $("tEnv").value, text, source };
        renderContractValidation(data.contract);
        renderTestValidation(data.ai_validation);
        renderReadiness(data);
        renderWorkflowTraceFromResponse(data, "tTrace");
        if (source === "voice_transcript") setVoiceStatus("Idle", "Voice transcript sent to the API.");
      } catch (e) {
        if ($("runStatus")) $("runStatus").textContent = "Error";
        if (source === "voice_transcript") setVoiceStatus("Error", e.message || "API call failed.");
        setConsoleOutput("tOut", e.data || { error: e.message });
      } finally {
        setRunLoading(false);
      }
    }

    function setRunLoading(isLoading) {
      if ($("runStatus")) {
        $("runStatus").textContent = isLoading ? "Running..." : ($("runStatus").textContent === "Running..." ? "Ready" : $("runStatus").textContent);
        $("runStatus").className = `pill ${isLoading ? "warning" : ""}`;
      }
      if ($("runTestBtn")) {
        $("runTestBtn").disabled = isLoading;
        $("runTestBtn").textContent = isLoading ? "Running..." : "Run";
      }
      if ($("eRunBtn")) {
        $("eRunBtn").disabled = isLoading;
        $("eRunBtn").textContent = isLoading ? "Running..." : "Run Email";
      }
    }

    function renderReadiness(data) {
      if (!$("tReadiness")) return;
      const summary = readinessSummary(data);
      $("tReadiness").className = `readiness ${summary.cls}`;
      $("tReadiness").innerHTML = summary.html;
    }

    function readinessSummary(data) {
      if (data.mode === "cmms-assistant") {
        return {
          cls: "warn",
          label: "Assistant chat response",
          html: '<strong>Assistant chat response</strong><div class="muted">Controlled advisory conversation only. No work order readiness decision, CMMS write-back, work order creation, or email sending.</div>'
        };
      }
      const validation = data.ai_validation;
      const legacy = data.validation;
      const contractOk = data.contract ? data.contract.valid : null;
      const envOk = validation ? validation.valid : null;
      const canCreate = legacy ? legacy.can_create_work_order : (contractOk === true && envOk === true);
      const missing = legacy?.missing_fields || [];
      const cls = canCreate ? "" : (envOk === false || contractOk === false ? "fail" : "warn");
      const label = canCreate ? "Ready for human-controlled workflow" : "Not ready for work order generation";
      return {
        cls,
        label,
        html: `<strong>${label}</strong><div class="muted">Advisory only. No work order was created.</div>
          <div style="margin-top:8px">Contract: <strong>${contractOk === null ? "n/a" : contractOk ? "passed" : "failed"}</strong> &nbsp; Environment: <strong>${envOk === null ? "n/a" : envOk ? "passed" : "failed"}</strong> &nbsp; Missing: <strong>${missing.length ? missing.join(", ") : "none"}</strong></div>`
      };
    }

    function renderContractValidation(contract) {
      if (!contract) { $("tContract").innerHTML = '<span class="muted">No output contract returned for this endpoint.</span>'; return; }
      const cls = contract.valid ? "ok" : "danger";
      $("tContract").innerHTML = `<div class="pill ${cls}">${contract.valid ? "Passed" : "Failed"}</div><span class="muted"> version ${escapeHtml(contract.version || "none")}</span>
        <h3>Errors</h3>${contract.errors?.length ? `<ul>${contract.errors.map(e=>`<li>${escapeHtml(e)}</li>`).join("")}</ul>` : '<p class="muted">None</p>'}
        <h3>Warnings</h3>${contract.warnings?.length ? `<ul>${contract.warnings.map(e=>`<li>${escapeHtml(e)}</li>`).join("")}</ul>` : '<p class="muted">None</p>'}`;
    }

    function renderTestValidation(validation) {
      if (!validation) { $("tValidation").innerHTML = '<span class="muted">No environment validation returned for this endpoint.</span>'; return; }
      const status = validation.valid ? (validation.warnings?.length ? "Passed with warnings" : "Passed") : "Failed";
      const cls = validation.valid ? "ok" : "danger";
      $("tValidation").innerHTML = `<div class="pill ${cls}">${status}</div>
        <h3>Errors</h3>${issueList(validation.errors)}
        <h3>Warnings</h3>${issueList(validation.warnings)}
        <h3>Normalized</h3><pre style="min-height:100px">${JSON.stringify(validation.normalized || {}, null, 2)}</pre>`;
    }

    async function renderWorkflowTraceFromResponse(data, targetId) {
      if (!$(targetId)) return;
      if (!data?.trace?.available || !data.trace.run_id) {
        $(targetId).innerHTML = '<span class="muted">No workflow trace for this response.</span>';
        return;
      }
      try {
        const trace = await api(`/api/admin/workflow-runs/${data.trace.run_id}`);
        $(targetId).innerHTML = renderWorkflowTrace(trace);
      } catch (e) {
        $(targetId).innerHTML = `<span class="muted">Trace ${escapeHtml(data.trace.run_id)} is available for admin users.</span>`;
      }
    }

    function renderWorkflowTrace(trace) {
      const icon = { passed: "✓", warning: "⚠", failed: "✕", skipped: "↷", running: "…" };
      const rows = (trace.steps || []).map(step => {
        const model = step.model ? ` — ${escapeHtml(step.model)}` : "";
        const prompt = step.prompt_version ? ` — ${escapeHtml(step.prompt_version)}` : "";
        const duration = step.duration_ms !== null && step.duration_ms !== undefined ? ` — ${step.duration_ms} ms` : "";
        const summary = step.output_summary || step.error_message || "";
        return `<div class="status-line" style="align-items:flex-start;border-bottom:1px solid #eef0f3;padding:8px 0">
          <div><strong>${icon[step.status] || "•"} ${escapeHtml(step.step_name.replaceAll("_", " "))}</strong><span class="muted">${model}${prompt}${duration}</span>${summary ? `<div class="muted">${escapeHtml(summary)}</div>` : ""}</div>
          <span class="pill ${step.status === "failed" ? "danger" : step.status === "warning" ? "warning" : step.status === "passed" ? "ok" : ""}">${escapeHtml(step.status)}</span>
        </div>`;
      }).join("");
      return `<div class="status-line"><strong>${escapeHtml(trace.run_id)}</strong><span class="pill ${trace.status === "failed" ? "danger" : trace.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(trace.status)}</span></div>${rows || '<p class="muted">No steps recorded.</p>'}`;
    }

    function renderWorkflowTrace(trace) {
      const icon = { passed: "OK", warning: "WARN", failed: "FAIL", skipped: "SKIP", running: "RUN" };
      const rows = (trace.steps || []).map(step => {
        const model = step.model ? ` - ${escapeHtml(step.model)}` : "";
        const prompt = step.prompt_version ? ` - ${escapeHtml(step.prompt_version)}` : "";
        const duration = step.duration_ms !== null && step.duration_ms !== undefined ? ` - ${step.duration_ms} ms` : "";
        const summary = step.output_summary || step.error_message || "";
        return `<div class="status-line" style="align-items:flex-start;border-bottom:1px solid #eef0f3;padding:8px 0">
          <div><strong>${icon[step.status] || "STEP"} ${escapeHtml(step.step_name.replaceAll("_", " "))}</strong><span class="muted">${model}${prompt}${duration}</span>${summary ? `<div class="muted">${escapeHtml(summary)}</div>` : ""}</div>
          <span class="pill ${step.status === "failed" ? "danger" : step.status === "warning" ? "warning" : step.status === "passed" ? "ok" : ""}">${escapeHtml(step.status)}</span>
        </div>`;
      }).join("");
      return `<div class="status-line"><strong>${escapeHtml(trace.run_id)}</strong><span class="pill ${trace.status === "failed" ? "danger" : trace.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(trace.status)}</span></div>
        <div class="row" style="margin:10px 0"><button class="secondary" onclick="createTestCaseFromTrace('${escapeAttr(trace.run_id)}')">Create Test Case from Run</button><button class="secondary" onclick="replayWorkflowRun('${escapeAttr(trace.run_id)}')">Replay Run</button></div>
        ${rows || '<p class="muted">No steps recorded.</p>'}`;
    }

    function issueList(items) {
      if (!items || !items.length) return '<p class="muted">None</p>';
      return `<ul>${items.map(i=>`<li><strong>${escapeHtml(i.field)}</strong>: ${escapeHtml(i.message)} <span class="muted">(${escapeHtml(i.value ?? "")})</span></li>`).join("")}</ul>`;
    }

    function outputToolbar(id) {
      return `<span class="row" style="gap:6px"><label style="margin:0;color:inherit"><input id="${id}Pretty" type="checkbox" checked onchange="refreshConsoleOutput('${id}')"> Pretty</label><button class="secondary" onclick="copyConsoleOutput('${id}')">Copy</button><button class="secondary" onclick="downloadConsoleOutput('${id}')">Download</button></span>`;
    }

    function setConsoleOutput(id, value, isJson = true) {
      state.outputs[id] = { value, isJson };
      refreshConsoleOutput(id);
    }

    function formatConsoleOutput(id) {
      const output = state.outputs[id];
      if (!output) return $(id)?.textContent || "";
      if (!output.isJson) return String(output.value ?? "");
      const pretty = $(`${id}Pretty`)?.checked !== false;
      return pretty ? JSON.stringify(output.value, null, 2) : JSON.stringify(output.value);
    }

    function refreshConsoleOutput(id) {
      if ($(id)) $(id).textContent = formatConsoleOutput(id);
    }

    async function copyConsoleOutput(id) {
      const text = formatConsoleOutput(id);
      await navigator.clipboard?.writeText(text);
    }

    function downloadConsoleOutput(id) {
      const text = formatConsoleOutput(id);
      const blob = new Blob([text], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${id}-${new Date().toISOString().replaceAll(":", "-")}.txt`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }

    function expectedFromResponse(response) {
      if (!response) return {};
      return {
        summary_contains: response.result?.summary ? [String(response.result.summary).slice(0, 40)] : [],
        building: response.result?.building ?? response.fields?.building ?? null,
        room: response.result?.room ?? response.fields?.room ?? null,
        priority: response.result?.priority ?? response.fields?.priority ?? null,
        work_order_type: response.result?.work_order_type ?? response.request_type ?? null,
        contract_valid: response.contract?.valid ?? null,
        environment_valid: response.ai_validation?.valid ?? null,
        expected_errors: [],
        expected_warnings: []
      };
    }

    function openSaveCurrentTestCase() {
      const current = state.lastTestInput || { endpoint: $("tEndpoint")?.value, environment_code: $("tEnv")?.value, text: $("tText")?.value, source: "manual" };
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="saveTestCaseModal"><div class="modal"><h2>Save Test Case</h2><div class="modal-body stack">
        <label>Name</label><input id="saveTcName" value="${escapeAttr((current.text || "CMMS request").slice(0, 60))}">
        <label>Endpoint</label><input id="saveTcEndpoint" value="${escapeAttr(current.endpoint || "cmms-intake")}">
        <label>Environment</label><input id="saveTcEnv" value="${escapeAttr(current.environment_code || "")}">
        <label>Input text</label><textarea id="saveTcText">${escapeHtml(current.text || "")}</textarea>
        <label>Expected JSON</label><textarea id="saveTcExpected" style="min-height:220px">${escapeHtml(JSON.stringify(expectedFromResponse(state.lastTestResponse), null, 2))}</textarea>
        <label>Tags</label><input id="saveTcTags" value="console">
        <label>Notes</label><textarea id="saveTcNotes"></textarea>
      </div><div class="modal-actions"><button class="secondary" onclick="closeSaveTestCaseModal()">Cancel</button><button onclick="saveCurrentTestCase()">Save</button></div></div></div>`);
    }

    function closeSaveTestCaseModal() { $("saveTestCaseModal")?.remove(); }

    async function saveCurrentTestCase() {
      let expected;
      try { expected = JSON.parse($("saveTcExpected").value); } catch { alert("Expected JSON is invalid."); return; }
      await api("/api/admin/test-cases", { method: "POST", body: JSON.stringify({ name: $("saveTcName").value, endpoint: $("saveTcEndpoint").value, environment_code: $("saveTcEnv").value || null, input_text: $("saveTcText").value, source: "console", expected_json: expected, enabled: true, tags: $("saveTcTags").value, notes: $("saveTcNotes").value }) });
      closeSaveTestCaseModal();
    }

    async function runMatchingTestCase() {
      const endpoint = $("tEndpoint")?.value || "cmms-intake";
      const environment = $("tEnv")?.value || "";
      const text = transcriptValue();
      const cases = await api(`/api/admin/test-cases?endpoint=${encodeURIComponent(endpoint)}&environment_code=${encodeURIComponent(environment)}&enabled=true`).catch(() => []);
      const match = cases.find(c => (c.input_text || "").trim() === text.trim());
      if (!match) {
        setConsoleOutput("tOut", { error: "No enabled saved test case matched the current endpoint, environment, and input text." });
        return;
      }
      const data = await api(`/api/admin/test-cases/${match.id}/run`, { method: "POST", body: JSON.stringify({}) });
      state.lastTestResponse = data.actual_json;
      setConsoleOutput("tOut", data);
      if (data.actual_json) {
        renderContractValidation(data.actual_json.contract);
        renderTestValidation(data.actual_json.ai_validation);
        renderReadiness(data.actual_json);
        renderWorkflowTraceFromResponse(data.actual_json, "tTrace");
      }
    }

    async function createTestCaseFromTrace(runId) {
      const name = window.prompt("Test case name", `Replay ${runId}`);
      if (!name) return;
      try {
        const data = await api(`/api/admin/workflow-runs/${runId}/create-test-case`, { method: "POST", body: JSON.stringify({ name, tags: "trace", notes: `Created from workflow run ${runId}` }) });
        alert(`Created test case #${data.test_case_id}`);
      } catch (e) {
        alert(e.message);
      }
    }

    async function replayWorkflowRun(runId) {
      try {
        const data = await api(`/api/admin/workflow-runs/${runId}/replay`, { method: "POST", body: JSON.stringify({}) });
        setConsoleOutput("tOut", data);
        if ($("logTraceDetail")) $("logTraceDetail").innerHTML = data.actual_json?.trace?.run_id ? `<p class="muted">Replay created workflow run ${escapeHtml(data.actual_json.trace.run_id)}.</p>` : "<p class='muted'>Replay completed.</p>";
        if (data.actual_json) renderWorkflowTraceFromResponse(data.actual_json, "tTrace");
      } catch (e) {
        if ($("tOut")) setConsoleOutput("tOut", e.data || { error: e.message });
        if ($("logTraceDetail")) $("logTraceDetail").innerHTML = `<span class="pill danger">Replay unavailable</span><p>${escapeHtml(e.message)}</p>`;
      }
    }

    async function testCases() {
      const cases = await api("/api/admin/test-cases").catch(() => []);
      const runs = await api("/api/admin/test-case-runs?limit=25").catch(() => []);
      pageShell("Test Cases", `<div class="grid">
        <div class="card span-8"><h2>Saved Test Cases</h2><div class="card-body stack">
          <div class="command-bar"><button onclick="newTestCase()">New</button><button class="secondary" onclick="runBatchTestCases()">Run Enabled Batch</button><button class="secondary" onclick="testCases()">Refresh</button></div>
          <div id="testCaseTable">${renderTestCasesTable(cases)}</div>
        </div></div>
        <div class="card span-4"><h2>Test Case Detail</h2><div class="card-body stack detail-form" id="testCaseDetail"><p class="muted">Select a test case or create a new one.</p></div></div>
        <div class="card span-12"><h2>Recent Test Case Runs</h2><div class="card-body" id="testCaseRuns">${renderTestCaseRunsTable(runs)}</div></div>
      </div>`);
    }

    function renderTestCasesTable(rows) {
      if (!rows.length) return '<p class="muted">No saved test cases yet.</p>';
      return `<table><thead><tr><th>Name</th><th>Endpoint</th><th>Environment</th><th>Enabled</th><th>Tags</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr class="clickable-row" onclick="showTestCaseDetail(${r.id})">
          <td><strong>${escapeHtml(r.name)}</strong><div class="muted">${escapeHtml((r.input_text || "").slice(0, 80))}</div></td>
          <td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td><span class="pill ${r.enabled ? "ok" : ""}">${r.enabled ? "enabled" : "disabled"}</span></td><td>${escapeHtml(r.tags || "")}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td class="row"><button class="secondary" onclick="event.stopPropagation(); runTestCaseId(${r.id})">Run</button><button class="secondary" onclick="event.stopPropagation(); showTestCaseDetail(${r.id})">Edit</button><button class="danger" onclick="event.stopPropagation(); toggleTestCase(${r.id}, ${r.enabled ? "false" : "true"})">${r.enabled ? "Disable" : "Enable"}</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function renderTestCaseRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No test case runs recorded yet.</p>';
      return `<table><thead><tr><th>Test Case</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Status</th><th>Duration</th><th>Started</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr><td>${escapeHtml(r.test_case_name || `#${r.test_case_id}`)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.prompt_version || "")}</td><td><span class="pill ${r.status === "passed" ? "ok" : r.status === "warning" ? "warning" : "danger"}">${escapeHtml(r.status)}</span></td><td>${r.duration_ms ?? ""} ms</td><td>${escapeHtml(r.started_at || "")}</td><td class="row"><button class="secondary" onclick="viewTestCaseRun('${escapeAttr(r.id)}')">View Result</button>${r.run_id ? `<button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(r.run_id)}')">View Trace</button>` : ""}</td></tr>`).join("")}</tbody></table>`;
    }

    function testCaseEndpointOptions(selected = "cmms-intake") {
      return ["cmms-intake","cmms-assistant","extract-work-order-fields","summarize-work-order"].map(v => `<option value="${v}" ${v === selected ? "selected" : ""}>${v}</option>`).join("");
    }

    function testCaseEnvOptions(selected = "") {
      return `<option value="" ${selected ? "" : "selected"}>None / request body defaults</option>${state.envs.map(e => `<option value="${e.environment_code}" ${e.environment_code === selected ? "selected" : ""}>${e.environment_code} - ${escapeHtml(e.name)}</option>`).join("")}`;
    }

    function renderTestCaseEditor(tc = null) {
      state.selectedTestCaseId = tc?.id || null;
      const expected = tc?.expected_json || { summary_contains: [], building: null, room: null, priority: null, work_order_type: null, contract_valid: true, environment_valid: true, expected_errors: [], expected_warnings: [] };
      $("testCaseDetail").innerHTML = `<label>Name</label><input id="tcName" value="${escapeAttr(tc?.name || "New CMMS regression case")}">
        <label>Endpoint</label><select id="tcEndpoint">${testCaseEndpointOptions(tc?.endpoint || "cmms-intake")}</select>
        <label>Environment</label><select id="tcEnv">${testCaseEnvOptions(tc?.environment_code || "DEFAULT")}</select>
        <label>Input text</label><textarea id="tcInput" style="min-height:120px">${escapeHtml(tc?.input_text || "There is a water leak in ARC room 205. It looks urgent.")}</textarea>
        <label>Expected JSON</label><textarea id="tcExpected" style="min-height:260px">${escapeHtml(JSON.stringify(expected, null, 2))}</textarea>
        <label>Tags</label><input id="tcTags" value="${escapeAttr(tc?.tags || "")}">
        <label>Notes</label><textarea id="tcNotes">${escapeHtml(tc?.notes || "")}</textarea>
        <label><input id="tcEnabled" type="checkbox" ${tc?.enabled === 0 ? "" : "checked"} style="width:auto"> Enabled</label>
        <div class="button-grid"><button onclick="saveTestCaseDetail()">Save</button><button class="secondary" onclick="runSelectedTestCase()">Run</button><button class="danger" onclick="deleteSelectedTestCase()" ${tc ? "" : "disabled"}>Delete</button></div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Run result</strong>${outputToolbar("tcResult")}</div><pre id="tcResult">{}</pre></div>`;
    }

    function newTestCase() { renderTestCaseEditor(null); }

    async function showTestCaseDetail(id) {
      const tc = await api(`/api/admin/test-cases/${id}`);
      renderTestCaseEditor(tc);
    }

    async function saveTestCaseDetail() {
      let expected;
      try { expected = JSON.parse($("tcExpected").value); } catch { alert("Expected JSON is invalid."); return; }
      const payload = { name: $("tcName").value, endpoint: $("tcEndpoint").value, environment_code: $("tcEnv").value || null, input_text: $("tcInput").value, expected_json: expected, enabled: $("tcEnabled").checked, tags: $("tcTags").value, notes: $("tcNotes").value };
      if (state.selectedTestCaseId) await api(`/api/admin/test-cases/${state.selectedTestCaseId}`, { method: "PATCH", body: JSON.stringify(payload) });
      else {
        const created = await api("/api/admin/test-cases", { method: "POST", body: JSON.stringify({ ...payload, source: "manual" }) });
        state.selectedTestCaseId = created.test_case_id;
      }
      await testCases();
    }

    async function runSelectedTestCase() {
      if (!state.selectedTestCaseId) await saveTestCaseDetail();
      if (state.selectedTestCaseId) await runTestCaseId(state.selectedTestCaseId);
    }

    async function runTestCaseId(id, promptId = null) {
      const data = await api(`/api/admin/test-cases/${id}/run`, { method: "POST", body: JSON.stringify({ prompt_id: promptId }) });
      if ($("tcResult")) setConsoleOutput("tcResult", data);
      if ($("testCaseRuns")) {
        const runs = await api("/api/admin/test-case-runs?limit=25").catch(() => []);
        $("testCaseRuns").innerHTML = renderTestCaseRunsTable(runs);
      }
      return data;
    }

    async function toggleTestCase(id, enabled) {
      await api(`/api/admin/test-cases/${id}`, { method: "PATCH", body: JSON.stringify({ enabled }) });
      await testCases();
    }

    async function deleteSelectedTestCase() {
      if (!state.selectedTestCaseId || !confirm("Delete this test case?")) return;
      await api(`/api/admin/test-cases/${state.selectedTestCaseId}`, { method: "DELETE" });
      state.selectedTestCaseId = null;
      await testCases();
    }

    async function viewTestCaseRun(id) {
      const data = await api(`/api/admin/test-case-runs/${id}`);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="testRunModal"><div class="modal" style="max-width:980px"><h2>Test Case Run</h2><div class="modal-body">
        <div class="result-grid"><div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Actual JSON</strong>${outputToolbar("testRunActual")}</div><pre id="testRunActual" style="min-height:300px"></pre></div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Comparison JSON</strong>${outputToolbar("testRunCompare")}</div><pre id="testRunCompare" style="min-height:300px"></pre></div></div>
      </div><div class="modal-actions"><button class="secondary" onclick="$('testRunModal').remove()">Close</button></div></div></div>`);
      setConsoleOutput("testRunActual", data.actual_json || {});
      setConsoleOutput("testRunCompare", data.comparison_json || {});
    }

    async function runBatchTestCases(promptId = null, endpoint = null) {
      const data = await api("/api/admin/test-cases/run-batch", { method: "POST", body: JSON.stringify({ endpoint, enabled_only: true, prompt_id: promptId }) });
      if ($("tcResult")) setConsoleOutput("tcResult", data);
      else alert(`Batch complete: ${data.passed}/${data.total} passed, ${data.failed} failed, ${data.warning} warning, ${data.error} error.`);
      if ($("testCaseRuns")) {
        const runs = await api("/api/admin/test-case-runs?limit=25").catch(() => []);
        $("testCaseRuns").innerHTML = renderTestCaseRunsTable(runs);
      }
      return data;
    }

    async function testSuites() {
      const suites = await api("/api/admin/test-suites").catch(() => []);
      const runs = await api("/api/admin/test-suite-runs?limit=25").catch(() => []);
      pageShell("Test Suites", `<div class="grid">
        <div class="card span-8"><h2>Suites</h2><div class="card-body stack">
          <div class="command-bar"><button onclick="newTestSuite()">New Suite</button><button class="secondary" onclick="runAllSuites()">Run Enabled Suites</button><button class="secondary" onclick="testSuites()">Refresh</button></div>
          <div id="testSuiteTable">${renderTestSuitesTable(suites)}</div>
        </div></div>
        <div class="card span-4"><h2>Suite Detail</h2><div class="card-body stack detail-form" id="testSuiteDetail"><p class="muted">Select a suite or create a new one.</p></div></div>
        <div class="card span-12"><h2>Suite Runs</h2><div class="card-body" id="testSuiteRuns">${renderTestSuiteRunsTable(runs)}</div></div>
      </div>`);
    }

    function renderTestSuitesTable(rows) {
      if (!rows.length) return '<p class="muted">No test suites yet.</p>';
      return `<table><thead><tr><th>Name</th><th>Endpoint</th><th>Environment</th><th>Enabled</th><th>Required</th><th>Min Pass</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${rows.map(s => `
        <tr class="clickable-row" onclick="showTestSuiteDetail('${escapeAttr(s.suite_id)}')"><td><strong>${escapeHtml(s.name)}</strong><div class="muted">${escapeHtml(s.tags || "")}</div></td><td>${escapeHtml(s.endpoint)}</td><td>${escapeHtml(s.environment_code || "")}</td><td><span class="pill ${s.enabled ? "ok" : ""}">${s.enabled ? "enabled" : "disabled"}</span></td><td>${s.required_for_promotion ? "Yes" : "No"}</td><td>${s.min_pass_rate}</td><td>${escapeHtml(s.updated_at || "")}</td><td class="row"><button class="secondary" onclick="event.stopPropagation(); showTestSuiteDetail('${escapeAttr(s.suite_id)}')">Edit</button><button class="secondary" onclick="event.stopPropagation(); runTestSuiteId('${escapeAttr(s.suite_id)}')">Run</button></td></tr>`).join("")}</tbody></table>`;
    }

    function renderTestSuiteRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No suite runs recorded yet.</p>';
      return `<table><thead><tr><th>Suite</th><th>Endpoint</th><th>Environment</th><th>Prompt</th><th>Status</th><th>Pass Rate</th><th>Started</th><th>Actions</th></tr></thead><tbody>${rows.map(r => {
        const s = r.summary_json || {};
        return `<tr><td>${escapeHtml(r.suite_name || r.suite_id)}</td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.prompt_version || "")}</td><td><span class="pill ${r.status === "passed" ? "ok" : r.status === "warning" ? "warning" : "danger"}">${escapeHtml(r.status)}</span></td><td>${s.pass_rate ?? ""}</td><td>${escapeHtml(r.started_at || "")}</td><td><button class="secondary" onclick="viewTestSuiteRun('${escapeAttr(r.suite_run_id)}')">View</button></td></tr>`;
      }).join("")}</tbody></table>`;
    }

    function renderTestSuiteEditor(suite = null) {
      const selectedEnv = suite?.environment_code || "DEFAULT";
      $("testSuiteDetail").innerHTML = `<label>Name</label><input id="tsName" value="${escapeAttr(suite?.name || "CMMS Intake Regression Suite")}">
        <label>Endpoint</label><select id="tsEndpoint">${testCaseEndpointOptions(suite?.endpoint || "cmms-intake")}</select>
        <label>Environment</label><select id="tsEnv">${testCaseEnvOptions(selectedEnv)}</select>
        <label>Description</label><textarea id="tsDescription">${escapeHtml(suite?.description || "")}</textarea>
        <label>Min pass rate</label><input id="tsMinPass" type="number" min="0" max="1" step="0.01" value="${suite?.min_pass_rate ?? 1}">
        <label><input id="tsEnabled" type="checkbox" ${suite?.enabled === 0 ? "" : "checked"} style="width:auto"> Enabled</label>
        <label><input id="tsRequired" type="checkbox" ${suite?.required_for_promotion ? "checked" : ""} style="width:auto"> Required for promotion</label>
        <label><input id="tsZeroError" type="checkbox" ${suite?.zero_error_required === 0 ? "" : "checked"} style="width:auto"> Zero error required</label>
        <label><input id="tsZeroRegression" type="checkbox" ${suite?.zero_regression_required === 0 ? "" : "checked"} style="width:auto"> Zero regression required</label>
        <label>Tags</label><input id="tsTags" value="${escapeAttr(suite?.tags || "")}">
        <div class="button-grid"><button onclick="saveTestSuite('${escapeAttr(suite?.suite_id || "")}')">Save</button><button class="secondary" onclick="runSelectedSuite('${escapeAttr(suite?.suite_id || "")}')">Run Suite</button><button class="danger" onclick="deleteTestSuite('${escapeAttr(suite?.suite_id || "")}')" ${suite ? "" : "disabled"}>Delete</button></div>
        <h3>Cases</h3><div id="suiteCases">${suite ? renderSuiteCases(suite.cases || []) : '<p class="muted">Save the suite before adding cases.</p>'}</div>
        ${suite ? `<label>Add Test Case ID</label><input id="suiteAddCaseId" placeholder="Test case id"><button class="secondary" onclick="addCaseToSuite('${escapeAttr(suite.suite_id)}')">Add Test Case</button>` : ""}
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Suite output</strong>${outputToolbar("suiteResult")}</div><pre id="suiteResult">{}</pre></div>`;
    }

    function renderSuiteCases(cases) {
      if (!cases.length) return '<p class="muted">No cases assigned.</p>';
      return `<table><thead><tr><th>ID</th><th>Name</th><th>Enabled</th><th>Action</th></tr></thead><tbody>${cases.map(c => `<tr><td>${c.test_case_id}</td><td>${escapeHtml(c.name)}</td><td>${c.enabled ? "Yes" : "No"}</td><td><button class="danger" onclick="removeCaseFromSuite('${escapeAttr(c.suite_id)}', ${c.test_case_id})">Remove</button></td></tr>`).join("")}</tbody></table>`;
    }

    function newTestSuite() { renderTestSuiteEditor(null); }

    async function showTestSuiteDetail(suiteId) {
      const suite = await api(`/api/admin/test-suites/${suiteId}`);
      renderTestSuiteEditor(suite);
    }

    async function saveTestSuite(suiteId) {
      const payload = { name: $("tsName").value, endpoint: $("tsEndpoint").value, environment_code: $("tsEnv").value || null, description: $("tsDescription").value, enabled: $("tsEnabled").checked, required_for_promotion: $("tsRequired").checked, min_pass_rate: Number($("tsMinPass").value), zero_error_required: $("tsZeroError").checked, zero_regression_required: $("tsZeroRegression").checked, tags: $("tsTags").value };
      if (suiteId) await api(`/api/admin/test-suites/${suiteId}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await api("/api/admin/test-suites", { method: "POST", body: JSON.stringify(payload) });
      await testSuites();
    }

    async function addCaseToSuite(suiteId) {
      await api(`/api/admin/test-suites/${suiteId}/cases`, { method: "POST", body: JSON.stringify({ test_case_id: Number($("suiteAddCaseId").value) }) });
      await showTestSuiteDetail(suiteId);
    }

    async function removeCaseFromSuite(suiteId, testCaseId) {
      await api(`/api/admin/test-suites/${suiteId}/cases/${testCaseId}`, { method: "DELETE" });
      await showTestSuiteDetail(suiteId);
    }

    async function runSelectedSuite(suiteId) {
      if (!suiteId) { alert("Save the suite before running."); return; }
      await runTestSuiteId(suiteId);
    }

    async function runTestSuiteId(suiteId, promptId = null) {
      const data = await api(`/api/admin/test-suites/${suiteId}/run`, { method: "POST", body: JSON.stringify({ prompt_id: promptId }) });
      if ($("suiteResult")) setConsoleOutput("suiteResult", data);
      await refreshTestSuiteRuns();
      return data;
    }

    async function refreshTestSuiteRuns() {
      if (!$("testSuiteRuns")) return;
      const runs = await api("/api/admin/test-suite-runs?limit=25").catch(() => []);
      $("testSuiteRuns").innerHTML = renderTestSuiteRunsTable(runs);
    }

    async function runAllSuites(promptId = null, endpoint = null, requiredOnly = false) {
      const data = await api("/api/admin/test-suites/run-batch", { method: "POST", body: JSON.stringify({ prompt_id: promptId, endpoint, required_only: requiredOnly, enabled_only: true }) });
      if ($("suiteResult")) setConsoleOutput("suiteResult", data);
      else alert(`Suite batch complete: ${data.passed}/${data.total_suites} passed, ${data.failed} failed, ${data.error} error.`);
      await refreshTestSuiteRuns();
      return data;
    }

    async function viewTestSuiteRun(suiteRunId) {
      const data = await api(`/api/admin/test-suite-runs/${suiteRunId}`);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="suiteRunModal"><div class="modal" style="max-width:1040px"><h2>Suite Run</h2><div class="modal-body">
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Suite run JSON</strong>${outputToolbar("suiteRunOut")}</div><pre id="suiteRunOut" style="min-height:360px"></pre></div>
      </div><div class="modal-actions"><button class="secondary" onclick="$('suiteRunModal').remove()">Close</button></div></div></div>`);
      setConsoleOutput("suiteRunOut", data);
    }

    async function deleteTestSuite(suiteId) {
      if (!suiteId || !confirm("Delete this test suite?")) return;
      await api(`/api/admin/test-suites/${suiteId}`, { method: "DELETE" });
      await testSuites();
    }

    function builder() {
      const base = location.origin;
      pageShell("API Call Builder", `<div class="grid">
        <div class="card span-4"><h2>Inputs</h2><div class="card-body stack">
          <label>Base URL</label><input id="bBase" value="${base}">
          <label>API key</label><input id="bKey" value="${escapeAttr(state.defaultApiKey)}">
          <label>Endpoint</label><select id="bEndpoint" onchange="buildCall()"><option value="cmms-intake">CMMS Intake</option><option value="intake/email">Email Intake</option><option value="cmms-assistant">CMMS Assistant</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select>
          <label>Environment</label><select id="bEnv" onchange="buildCall()">${envOptions()}</select>
          <label>Input source</label><select id="bSource" onchange="buildCall()"><option value="text">text</option><option value="voice_transcript">voice_transcript</option><option value="email_paste">email_paste</option><option value="email_mailbox">email_mailbox_reserved</option></select>
          <label>Text</label><textarea id="bText" oninput="buildCall()">The air conditioner in ARC room 205 is making loud noise.</textarea>
          <label><input id="bReturnValidation" type="checkbox" checked style="width:auto" onchange="buildCall()"> Include readiness validation in examples</label>
          <div class="button-grid"><button onclick="buildCall()">Generate</button><button class="secondary" onclick="runBuilderValidation()">Run + Validate</button></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Generated calls</div><div class="playground-subtitle">PowerShell, curl, request body, response contract, and readiness logic.</div></div><span class="pill">Builder</span></div><div class="run-surface">
          <div id="bDoc" class="ai-panel"></div>
          <div id="bValidationOut" class="readiness warn"><strong>Validation preview</strong><div class="muted">Use Run + Validate to call the endpoint and check whether the response has enough validated information.</div></div>
          <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Generated examples</strong>${outputToolbar("bOut")}</div><pre id="bOut" class="code-output"></pre></div>
        </div></div>
      </div>`);
      buildCall();
    }
    function buildCall() {
      const ep = $("bEndpoint").value;
      const bodyObj = builderRequestBody(ep);
      const body = JSON.stringify(bodyObj, null, 2);
      const uri = `${$("bBase").value}/api/ai/${ep}`;
      const includeValidation = $("bReturnValidation").checked && (ep === "cmms-intake" || ep === "intake/email");
      const psValidation = includeValidation ? `\n\n# Readiness check: advisory only, does not create a work order\n$ContractOk = $Response.contract.valid\n$EnvironmentOk = $Response.ai_validation.valid\n$CanCreateWorkOrder = $Response.validation.can_create_work_order\n$MissingFields = $Response.validation.missing_fields -join ", "\n[pscustomobject]@{\n  ContractValidation = $ContractOk\n  EnvironmentValidation = $EnvironmentOk\n  EnoughInformation = $CanCreateWorkOrder\n  MissingFields = $MissingFields\n  AdvisoryOnly = $true\n}` : "";
      const ps = `$Headers = @{ "x-api-key" = "${$("bKey").value}" }\n$Body = @'\n${body}\n'@\n$Response = Invoke-RestMethod -Method POST -Uri "${uri}" -Headers $Headers -ContentType "application/json" -Body $Body\n$Response | ConvertTo-Json -Depth 20${psValidation}`;
      const curl = `curl -X POST "${uri}" \\\n  -H "x-api-key: ${$("bKey").value}" \\\n  -H "Content-Type: application/json" \\\n  -d '${body.replaceAll("'", "\\'")}'`;
      const responseNotes = endpointDoc(ep, includeValidation);
      $("bDoc").innerHTML = responseNotes;
      setConsoleOutput("bOut", `PowerShell:\n${ps}\n\ncurl:\n${curl}\n\nJSON body:\n${body}\n\nExpected response fields:\n${expectedFields(ep).join("\\n")}`, false);
    }

    function builderRequestBody(endpoint) {
      if (endpoint === "intake/email") {
        return {
          from_email: "tenant@example.com",
          to_email: "maintenance@example.com",
          submitted_by: "John Smith",
          submitted_phone: "416-555-0101",
          requested_due_at: "2026-05-24T17:00:00Z",
          location: { raw: "ARC room 205", building: "ARC", room: "205", area: null },
          subject: "Leak in ARC 205",
          body: $("bText").value,
          environment_code: $("bEnv").value
        };
      }
      const bodyObj = { text: $("bText").value, environment_code: $("bEnv").value };
      if ($("bSource").value !== "text") bodyObj.source = $("bSource").value;
      if (endpoint === "cmms-intake") {
        bodyObj.submission = {
          submitted_by: "John Smith",
          submitted_email: "john@example.com",
          submitted_phone: "416-555-0101",
          submitted_method: $("bSource").value === "voice_transcript" ? "voice_transcript" : "api"
        };
        bodyObj.request = {
          requested_due_at: "2026-05-24T17:00:00Z",
          location: { raw: "ARC room 205", building: "ARC", room: "205", area: null }
        };
      }
      return bodyObj;
    }

    function endpointDoc(endpoint, includeValidation) {
      const docs = {
        "cmms-intake": ["POST /api/ai/cmms-intake", "Returns endpoint, environment_code, contract validation, result, ai_validation, advisory validation, drafts, and model.", "Use contract.valid plus ai_validation.valid plus validation.can_create_work_order to decide if the request has enough information for a human-controlled CMMS workflow."],
        "intake/email": ["POST /api/ai/intake/email", "Accepts email fields, submission metadata, requested due date, and location.", "Runs the same advisory intake workflow with source email_api."],
        "cmms-assistant": ["POST /api/ai/cmms-assistant", "Returns a controlled conversational CMMS assistant response and safety flags.", "This is not a generic /chat endpoint. It is advisory-only and cannot write to CMMS, create work orders, or send emails."],
        "extract-work-order-fields": ["POST /api/ai/extract-work-order-fields", "Returns extracted request_type, building, room, priority, summary, missing_fields, needs_human_review, and confidence.", "Use missing_fields and needs_human_review to decide if a human must complete the request."],
        "summarize-work-order": ["POST /api/ai/summarize-work-order", "Returns one summary string.", "This endpoint does not validate work order readiness."]
      };
      const lines = docs[endpoint] || docs["cmms-intake"];
      return `<strong>${escapeHtml(lines[0])}</strong><p class="muted">${escapeHtml(lines[1])}</p><p>${escapeHtml(lines[2])}</p>${includeValidation ? '<span class="pill ok">Readiness logic included</span>' : '<span class="pill">Readiness logic not applicable</span>'}`;
    }

    function expectedFields(endpoint) {
      if (endpoint === "summarize-work-order") return ["- summary: string"];
      if (endpoint === "cmms-assistant") return ["- mode: cmms-assistant", "- response: string", "- model: qwen3:8b", "- safety.advisory_only: true", "- safety.work_order_created: false"];
      if (endpoint === "extract-work-order-fields") return ["- request_type: string", "- building: string|null", "- room: string|null", "- priority: string", "- missing_fields: array", "- needs_human_review: boolean", "- confidence: number"];
      return ["- contract.valid: boolean", "- result: normalized contract payload", "- ai_validation.valid: boolean|null", "- ai_validation.errors/warnings/normalized", "- validation.can_create_work_order: boolean advisory flag", "- validation.missing_fields: array", "- drafts: advisory text only"];
    }

    async function runBuilderValidation() {
      const ep = $("bEndpoint").value;
      const body = builderRequestBody(ep);
      try {
        const data = await api(`/api/ai/${ep}`, { method: "POST", headers: { "x-api-key": $("bKey").value }, body: JSON.stringify(body) });
        if (ep === "cmms-intake") {
          const summary = readinessSummary(data);
          $("bValidationOut").className = `readiness ${summary.cls}`;
          $("bValidationOut").innerHTML = summary.html;
        } else if (ep === "extract-work-order-fields") {
          $("bValidationOut").className = `readiness ${data.needs_human_review ? "warn" : ""}`;
          $("bValidationOut").innerHTML = `<strong>${data.needs_human_review ? "Needs human review" : "Basic extraction complete"}</strong><div class="muted">Missing fields: ${(data.missing_fields || []).join(", ") || "none"}</div>`;
        } else if (ep === "cmms-assistant") {
          $("bValidationOut").className = "readiness warn";
          $("bValidationOut").innerHTML = '<strong>Assistant response</strong><div class="muted">Controlled advisory chat only. No readiness validation and no CMMS action.</div>';
        } else {
          $("bValidationOut").className = "readiness warn";
          $("bValidationOut").innerHTML = '<strong>Summary only</strong><div class="muted">This endpoint does not return readiness validation.</div>';
        }
        setConsoleOutput("bOut", `${formatConsoleOutput("bOut")}\n\nLive response:\n${JSON.stringify(data, null, 2)}`, false);
      } catch (e) {
        $("bValidationOut").className = "readiness fail";
        $("bValidationOut").innerHTML = `<strong>API call failed</strong><div class="muted">${escapeHtml(e.message)}</div>`;
      }
    }
    async function environments() {
      await refreshBase();
      if (!state.envs.some(e => e.environment_code === state.selectedEnv)) state.selectedEnv = state.envs[0]?.environment_code || "DEFAULT";
      await loadEnvironmentCodes();
      await loadValidationRules();
      const env = state.envs.find(e => e.environment_code === state.selectedEnv) || {};
      pageShell("Environments", `<div class="resource-header">
        <div class="resource-title">Environment: ${env.environment_code || state.selectedEnv}</div>
        <div class="muted">Status: ${env.enabled ? "Enabled" : "Disabled"} &nbsp; Model: qwen3:8b &nbsp; Base URL: local &nbsp; Updated: ${env.updated_at || ""}</div>
      </div>
      <div class="command-bar">
        <span class="muted">Environment</span><select id="envPick" onchange="state.selectedEnv=this.value; environments()">${state.envs.map(e=>`<option value="${e.environment_code}" ${e.environment_code===state.selectedEnv?"selected":""}>${e.environment_code} - ${e.name}</option>`).join("")}</select>
        <button class="secondary" onclick="showCreateEnv()">Create environment</button>
        <button class="secondary" onclick="environments()">Refresh</button>
      </div>
      <div class="tabs">
        <button class="${state.envTab==='codes'?'active':''}" onclick="state.envTab='codes'; renderEnvironmentTab()">Code Lists</button>
        <button class="${state.envTab==='validation'?'active':''}" onclick="state.envTab='validation'; renderEnvironmentTab()">Validation Rules</button>
        <button disabled>Overview</button><button disabled>Test Console</button><button disabled>API Examples</button><button disabled>Usage Logs</button><button disabled>Settings</button>
      </div>
      <div id="envTab">${state.envTab === 'validation' ? renderValidationRulesTab() : renderCodeListsTab()}</div>`);
    }
    async function createEnv() {
      await api("/api/admin/environments", { method: "POST", body: JSON.stringify({ environment_code: $("envCode").value, name: $("envName").value, enabled: true }) });
      await refreshBase(); environments();
    }

    function showCreateEnv() {
      const code = prompt("Environment code", "TEST");
      if (!code) return;
      const name = prompt("Environment name", "Test Environment") || code;
      api("/api/admin/environments", { method: "POST", body: JSON.stringify({ environment_code: code, name, enabled: true }) }).then(async () => { await refreshBase(); state.selectedEnv = code.toUpperCase(); environments(); });
    }

    async function loadEnvironmentCodes() {
      state.codeData = await api(`/api/admin/environments/${state.selectedEnv}/codes`).catch(() => ({ rows: [] }));
    }

    async function loadValidationRules() {
      state.validationRules = await api(`/api/environments/${state.selectedEnv}/validation-rules`).catch(() => []);
    }

    function renderEnvironmentTab() {
      $("envTab").innerHTML = state.envTab === "validation" ? renderValidationRulesTab() : renderCodeListsTab();
    }

    function currentCodeRows() {
      const search = ($("codeSearch")?.value || "").toLowerCase();
      return (state.codeData?.rows || []).filter(r => r.category === state.selectedCategory).filter(r => !search || `${r.code} ${r.label} ${r.aliases || ""}`.toLowerCase().includes(search));
    }

    function categoryLabel(category) {
      return (codeCategories.find(c => c[0] === category) || [category, category])[1];
    }

    function renderCodeListsTab() {
      const rows = currentCodeRows();
      const selected = state.selectedCode || rows[0] || null;
      state.selectedCode = selected;
      return `<div class="command-bar">
        <strong>Code Lists</strong><span class="muted">Manage controlled input values used by AI extraction and validation.</span>
        <select id="codeCategory" onchange="changeCodeCategory(this.value)">${codeCategories.map(([v,l])=>`<option value="${v}" ${v===state.selectedCategory?"selected":""}>${l}</option>`).join("")}</select>
        <input id="codeSearch" placeholder="Search code or description" oninput="renderCodesOnly()">
        <button onclick="openImportModal()">Import</button><button class="secondary" onclick="exportCodes()">Export</button><button class="secondary" onclick="validateSample()">Validate Sample</button><button class="secondary" onclick="environments()">Refresh</button>
      </div>
      <div class="muted" style="margin-bottom:10px">Environment: <strong>${state.selectedEnv}</strong> / Category: <strong>${categoryLabel(state.selectedCategory)}</strong></div>
      <div class="blade-layout">
        <div class="card"><h2>${categoryLabel(state.selectedCategory)}</h2><div class="card-body">${renderCodeTable(rows)}</div></div>
        <div class="blade" id="codeBlade">${renderCodeBlade(selected)}</div>
      </div>`;
    }

    function renderCodesOnly() {
      state.selectedCategory = $("codeCategory").value;
      $("envTab").innerHTML = renderCodeListsTab();
    }

    async function changeCodeCategory(category) {
      state.selectedCategory = category;
      state.selectedCode = null;
      await loadEnvironmentCodes();
      renderCodesOnly();
    }

    function renderCodeTable(rows) {
      if (!rows.length) return `<p class="muted">No codes for this category. Use Import to add values.</p>`;
      return `<table><thead><tr><th>Code</th><th>Description</th><th>Status</th><th>Source</th><th>Updated At</th><th>Actions</th></tr></thead><tbody>${rows.map(r=>`
        <tr class="clickable-row" onclick="selectCode(${r.code_id})">
          <td><strong>${escapeHtml(r.code)}</strong></td><td>${escapeHtml(r.label || "")}</td><td>${r.enabled ? '<span class="pill ok">Enabled</span>' : '<span class="pill danger">Disabled</span>'}</td><td>${escapeHtml(r.source || "Manual")}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td><button class="secondary" onclick="event.stopPropagation(); selectCode(${r.code_id})">Edit</button> <button class="secondary" onclick="event.stopPropagation(); disableCode(${r.code_id})">Disable</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function selectCode(codeId) {
      state.selectedCode = (state.codeData?.rows || []).find(r => r.code_id === codeId);
      $("codeBlade").innerHTML = renderCodeBlade(state.selectedCode);
    }

    function renderCodeBlade(row) {
      if (!row) return `<h2>Edit Code</h2><div class="blade-body muted">Select a code row to edit details.</div>`;
      const defaultMetadata = JSON.stringify({ site: "main", active: true }, null, 2);
      return `<h2>Edit Code</h2><div class="blade-body stack">
        <label>Code</label><input id="editCode" value="${escapeAttr(row.code)}">
        <label>Description</label><input id="editLabel" value="${escapeAttr(row.label || "")}">
        <label>Aliases</label><input id="editAliases" value="${escapeAttr(row.aliases || "")}" placeholder="ARC, Arc Building">
        <label>Metadata JSON</label><textarea id="editMetadata">${escapeHtml(row.metadata_json || defaultMetadata)}</textarea>
        <div class="row"><button onclick="saveCode(${row.code_id})">Save</button><button class="danger" onclick="disableCode(${row.code_id})">Disable</button></div>
      </div>`;
    }

    async function saveCode(codeId) {
      await api(`/api/admin/environments/${state.selectedEnv}/codes/${codeId}`, { method: "PATCH", body: JSON.stringify({ code: $("editCode").value, label: $("editLabel").value, aliases: $("editAliases").value, metadata_json: $("editMetadata").value, enabled: true }) });
      await loadEnvironmentCodes(); renderCodesOnly();
    }

    async function disableCode(codeId) {
      await api(`/api/admin/environments/${state.selectedEnv}/codes/${codeId}`, { method: "PATCH", body: JSON.stringify({ enabled: false }) });
      await loadEnvironmentCodes(); renderCodesOnly();
    }

    function openImportModal() {
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="importModal"><div class="modal"><h2>Import ${categoryLabel(state.selectedCategory)}</h2><div class="modal-body stack">
        <p class="muted">Paste codes or upload a CSV file. Format: Code, Description, Aliases, Metadata JSON</p>
        <label>CSV file</label><input id="importFile" type="file" accept=".csv,text/csv" onchange="readImportFile()">
        <textarea id="importText">ARC, ARC Building\nCAMPUSVIEW, Campus View\nZONE-18, Zone 18</textarea>
        <label><input id="importReplace" type="checkbox" style="width:auto"> Replace this category before importing</label>
        <div id="previewBox" class="muted">Preview results will appear here.</div>
      </div><div class="modal-actions"><button class="secondary" onclick="closeImportModal()">Cancel</button><button class="secondary" onclick="previewImport()">Preview Import</button><button onclick="commitImport()">Import</button></div></div></div>`);
    }

    function closeImportModal() { $("importModal")?.remove(); }

    function readImportFile() {
      const file = $("importFile")?.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => { $("importText").value = String(reader.result || ""); previewImport(); };
      reader.onerror = () => { $("previewBox").innerHTML = '<span class="pill danger">Could not read CSV file.</span>'; };
      reader.readAsText(file);
    }

    async function previewImport() {
      const data = await api(`/api/admin/environments/${state.selectedEnv}/codes/preview`, { method: "POST", body: JSON.stringify({ category: state.selectedCategory, text: $("importText").value, replace: $("importReplace")?.checked || false }) });
      $("previewBox").innerHTML = `<div class="preview-summary"><div><strong>${data.valid_count}</strong><br>valid</div><div><strong>${data.duplicate_count}</strong><br>duplicates</div><div><strong>${data.invalid_count}</strong><br>invalid</div><div><strong>${data.update_count}</strong><br>existing updated</div><div><strong>${data.insert_count}</strong><br>new inserted</div></div>${renderImportPreviewTable(data)}`;
    }

    async function commitImport() {
      await api(`/api/admin/environments/${state.selectedEnv}/codes/import`, { method: "POST", body: JSON.stringify({ category: state.selectedCategory, text: $("importText").value, replace: $("importReplace")?.checked || false }) });
      closeImportModal(); await loadEnvironmentCodes(); renderCodesOnly();
    }

    function renderImportPreviewTable(data) {
      const rows = (data.valid || []).slice(0, 25);
      if (!rows.length) return '<p class="muted">No valid rows in preview.</p>';
      return `<table><thead><tr><th>Code</th><th>Description</th><th>Aliases</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr><td><strong>${escapeHtml(r.code)}</strong></td><td>${escapeHtml(r.label || "")}</td><td>${escapeHtml(r.aliases || "")}</td><td>${(data.category && (data.valid || []).some(x => x.code === r.code)) ? "Import/update" : "Import"}</td></tr>`).join("")}</tbody></table>`;
    }

    function exportCodes() {
      const csv = currentCodeRows().map(r => [r.code, r.label || "", r.aliases || ""].map(v => `"${String(v).replaceAll('"','""')}"`).join(",")).join("\\n");
      navigator.clipboard?.writeText(csv); alert("Current table copied as CSV.");
    }

    function validateSample() { alert("Validation Rules is the next resource tab. For now, code-list duplicate and metadata validation run during import/edit."); }

    function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
    function escapeAttr(value) { return escapeHtml(value).replaceAll("`", "&#96;"); }

    function renderValidationRulesTab() {
      return `<div class="command-bar">
        <strong>Validation Rules</strong><span class="muted">These rules validate AI output after extraction. They do not change the model prompt.</span>
        <button class="secondary" onclick="resetValidationRules()">Reset Defaults</button>
        <button class="secondary" onclick="openValidateSampleModal()">Validate Sample</button>
        <button class="secondary" onclick="refreshValidationRules()">Refresh</button>
      </div>
      <div class="card"><h2>Rules</h2><div class="card-body">${renderValidationTable()}</div></div>`;
    }

    function renderValidationTable() {
      if (!state.validationRules.length) return '<p class="muted">No validation rules configured.</p>';
      return `<table><thead><tr><th>Field</th><th>Required</th><th>Match Code List</th><th>Category</th><th>Allow Unknown</th><th>Severity</th><th>Enabled</th><th>Actions</th></tr></thead><tbody>${state.validationRules.map(r=>`
        <tr>
          <td><strong>${escapeHtml(r.label)}</strong><div class="muted">${escapeHtml(r.field_name)}</div></td>
          <td>${r.required ? "Yes" : "No"}</td>
          <td>${r.must_match_code_list ? "Yes" : "No"}</td>
          <td>${escapeHtml(r.code_category || "")}</td>
          <td>${r.allow_unknown ? "Yes" : "No"}</td>
          <td>${r.severity === "error" ? '<span class="pill danger">Error</span>' : '<span class="pill">Warning</span>'}</td>
          <td>${r.enabled ? '<span class="pill ok">Yes</span>' : '<span class="pill danger">No</span>'}</td>
          <td><button class="secondary" onclick="editValidationRule(${r.id})">Edit</button> <button class="secondary" onclick="toggleValidationRule(${r.id}, ${r.enabled ? "false" : "true"})">${r.enabled ? "Disable" : "Enable"}</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    async function refreshValidationRules() {
      await loadValidationRules();
      renderEnvironmentTab();
    }

    async function toggleValidationRule(ruleId, enabled) {
      await api(`/api/admin/environments/${state.selectedEnv}/validation-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify({ enabled }) });
      await refreshValidationRules();
    }

    function editValidationRule(ruleId) {
      const rule = state.validationRules.find(r => r.id === ruleId);
      if (!rule) return;
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="ruleModal"><div class="modal"><h2>Edit ${escapeHtml(rule.label)}</h2><div class="modal-body stack">
        <label><input id="ruleEnabled" type="checkbox" ${rule.enabled ? "checked" : ""} style="width:auto"> Enabled</label>
        <label><input id="ruleRequired" type="checkbox" ${rule.required ? "checked" : ""} style="width:auto"> Required</label>
        <label><input id="ruleMatch" type="checkbox" ${rule.must_match_code_list ? "checked" : ""} style="width:auto"> Must match code list</label>
        <label><input id="ruleUnknown" type="checkbox" ${rule.allow_unknown ? "checked" : ""} style="width:auto"> Allow unknown value</label>
        <label>Category mapping</label><select id="ruleCategory">${codeCategories.map(([v,l])=>`<option value="${v}" ${v===rule.code_category?"selected":""}>${l}</option>`).join("")}</select>
        <label>Severity</label><select id="ruleSeverity"><option value="error" ${rule.severity==="error"?"selected":""}>error</option><option value="warning" ${rule.severity==="warning"?"selected":""}>warning</option></select>
      </div><div class="modal-actions"><button class="secondary" onclick="closeRuleModal()">Cancel</button><button onclick="saveValidationRule(${rule.id})">Save</button></div></div></div>`);
    }

    function closeRuleModal() { $("ruleModal")?.remove(); }

    async function saveValidationRule(ruleId) {
      await api(`/api/admin/environments/${state.selectedEnv}/validation-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify({ enabled: $("ruleEnabled").checked, required: $("ruleRequired").checked, must_match_code_list: $("ruleMatch").checked, allow_unknown: $("ruleUnknown").checked, code_category: $("ruleCategory").value, severity: $("ruleSeverity").value }) });
      closeRuleModal(); await refreshValidationRules();
    }

    async function resetValidationRules() {
      if (!confirm("Reset validation rules for this environment to defaults?")) return;
      await api(`/api/admin/environments/${state.selectedEnv}/validation-rules/reset-defaults`, { method: "POST" });
      await refreshValidationRules();
    }

    function openValidateSampleModal() {
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="sampleModal"><div class="modal"><h2>Validate Sample</h2><div class="modal-body stack">
        <textarea id="sampleJson">{\n  "building": "ARC",\n  "room": "101",\n  "priority": "HIGH",\n  "work_order_type": "PM",\n  "assign_to": "1001",\n  "issue_to": "2001",\n  "job_type": "ELEC"\n}</textarea>
        <div id="sampleResult" class="muted">Run validation to see pass/fail.</div>
      </div><div class="modal-actions"><button class="secondary" onclick="closeSampleModal()">Close</button><button onclick="runSampleValidation()">Validate</button></div></div></div>`);
    }

    function closeSampleModal() { $("sampleModal")?.remove(); }

    async function runSampleValidation() {
      let values;
      try { values = JSON.parse($("sampleJson").value); } catch { $("sampleResult").innerHTML = '<span class="pill danger">Invalid JSON</span>'; return; }
      const data = await api(`/api/environments/${state.selectedEnv}/validate-sample`, { method: "POST", body: JSON.stringify({ values }) });
      $("sampleResult").innerHTML = `<div class="pill ${data.valid ? "ok" : "danger"}">${data.valid ? "Passed" : "Failed"}</div><pre style="min-height:160px">${JSON.stringify(data, null, 2)}</pre>`;
    }
    async function contracts() {
      const data = await api("/api/admin/output-contracts");
      pageShell("AI Output Contracts", `<div class="contracts-layout">
        <div class="card"><h2>Contracts</h2><div class="card-body">${renderContractsTable(data)}</div></div>
        <div class="card"><h2>Contract Detail</h2><div class="card-body stack detail-form" id="contractDetail"><p class="muted">Select a contract to view or edit.</p></div></div>
      </div>`);
    }

    function renderContractsTable(rows) {
      if (!rows.length) return '<p class="muted">No output contracts configured.</p>';
      return `<table><thead><tr><th>Endpoint</th><th>Version</th><th>Status</th><th>Strict Mode</th><th>Updated At</th><th>Actions</th></tr></thead><tbody>${rows.map(r=>`
        <tr class="clickable-row" onclick='showContractDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>
          <td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.version)}</td><td>${r.status === "active" ? '<span class="pill ok">active</span>' : `<span class="pill">${escapeHtml(r.status)}</span>`}</td><td>${r.strict_mode ? "Yes" : "No"}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td><button class="secondary" onclick='event.stopPropagation(); showContractDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>View / Edit / Test</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function showContractDetail(contract) {
      $("contractDetail").innerHTML = `<label>Endpoint</label><input id="contractEndpoint" value="${escapeAttr(contract.endpoint)}" disabled>
        <label>Version</label><input id="contractVersion" value="${escapeAttr(contract.version)}" disabled>
        <label>Name</label><input id="contractName" value="${escapeAttr(contract.name)}">
        <label>Status</label><select id="contractStatus"><option ${contract.status==="draft"?"selected":""}>draft</option><option ${contract.status==="active"?"selected":""}>active</option><option ${contract.status==="archived"?"selected":""}>archived</option></select>
        <label><input id="contractStrict" type="checkbox" ${contract.strict_mode ? "checked" : ""} style="width:auto"> Strict mode</label>
        <label>Schema JSON</label><textarea id="contractSchema" style="min-height:360px">${escapeHtml(JSON.stringify(contract.schema_json, null, 2))}</textarea>
        <label>Sample Payload</label><textarea id="contractSample">{
  "summary": "Air conditioner in ARC room 205 is noisy.",
  "building": "ARC",
  "room": "205",
  "priority": "NORMAL",
  "work_order_type": "HVAC",
  "assign_to": null,
  "issue_to": null,
  "job_type": null,
  "confidence": 0.86
}</textarea>
        <div class="row"><button onclick="saveContract(${contract.id})">Save</button><button class="secondary" onclick="activateContract(${contract.id})">Activate</button><button class="secondary" onclick="testContract(${contract.id})">Test Sample</button></div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Sample validation</strong>${outputToolbar("contractResult")}</div><pre id="contractResult" style="min-height:160px">{}</pre></div>`;
    }

    async function saveContract(id) {
      let schema;
      try { schema = JSON.parse($("contractSchema").value); } catch { alert("Schema JSON is invalid."); return; }
      await api(`/api/admin/output-contracts/${id}`, { method: "PATCH", body: JSON.stringify({ name: $("contractName").value, status: $("contractStatus").value, schema_json: schema, strict_mode: $("contractStrict").checked }) });
      contracts();
    }

    async function activateContract(id) {
      await api(`/api/admin/output-contracts/${id}/activate`, { method: "POST" });
      contracts();
    }

    async function testContract(id) {
      let values;
      try { values = JSON.parse($("contractSample").value); } catch { setConsoleOutput("contractResult", { error: "Invalid sample JSON" }); return; }
      const data = await api(`/api/admin/output-contracts/${id}/validate-sample`, { method: "POST", body: JSON.stringify({ values }) });
      setConsoleOutput("contractResult", data);
    }

    async function prompts() {
      const data = await api("/api/admin/prompt-versions");
      const comparisons = await api("/api/admin/prompt-comparisons?limit=25").catch(() => []);
      const promotions = await api("/api/admin/prompt-promotions?limit=25").catch(() => []);
      pageShell("Prompt Versions", `<div class="contracts-layout">
        <div class="card"><h2>Prompts</h2><div class="card-body">${renderPromptsTable(data)}</div></div>
        <div class="card"><h2>Prompt Detail</h2><div class="card-body stack detail-form" id="promptDetail"><p class="muted">Select a prompt to view, test, edit, activate, or archive.</p></div></div>
        <div class="card"><h2>Prompt Comparisons</h2><div class="card-body" id="promptComparisons">${renderPromptComparisonsTable(comparisons)}</div></div>
        <div class="card"><h2>Comparison Detail</h2><div class="card-body" id="promptComparisonDetail"><p class="muted">Run or view a comparison to see deterministic regression results.</p></div></div>
        <div class="card"><h2>Promotion History</h2><div class="card-body" id="promptPromotions">${renderPromptPromotionsTable(promotions)}</div></div>
      </div>`);
    }

    function renderPromptsTable(rows) {
      if (!rows.length) return '<p class="muted">No prompt versions configured.</p>';
      return `<table><thead><tr><th>Endpoint</th><th>Version</th><th>Status</th><th>Model</th><th>Temperature</th><th>Updated</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr class="clickable-row" onclick='showPromptDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>
          <td><strong>${escapeHtml(r.endpoint)}</strong><div class="muted">${escapeHtml(r.name)}</div></td>
          <td>${escapeHtml(r.version)}</td>
          <td><span class="pill ${r.status === "active" ? "ok" : r.status === "archived" ? "danger" : ""}">${escapeHtml(r.status)}</span></td>
          <td>${escapeHtml(r.model)}</td><td>${r.temperature}</td><td>${escapeHtml(r.updated_at || "")}</td>
          <td><button class="secondary" onclick='event.stopPropagation(); showPromptDetail(${JSON.stringify(r).replaceAll("'", "&#39;")})'>View / Test</button></td>
        </tr>`).join("")}</tbody></table>`;
    }

    function showPromptDetail(prompt) {
      const readonly = prompt.status === "archived" ? "disabled" : "";
      $("promptDetail").innerHTML = `<div class="row"><span class="pill ${prompt.status === "active" ? "ok" : prompt.status === "archived" ? "danger" : ""}">${escapeHtml(prompt.status)}</span><span class="muted">${escapeHtml(prompt.endpoint)} / ${escapeHtml(prompt.version)}</span></div>
        <label>Endpoint</label><input id="promptEndpoint" value="${escapeAttr(prompt.endpoint)}" disabled>
        <label>Version</label><input id="promptVersion" value="${escapeAttr(prompt.version)}" disabled>
        <label>Name</label><input id="promptName" value="${escapeAttr(prompt.name)}" ${readonly}>
        <label>Model</label><input id="promptModel" value="${escapeAttr(prompt.model)}" ${readonly}>
        <label>Temperature</label><input id="promptTemperature" type="number" step="0.1" min="0" max="2" value="${prompt.temperature}" ${readonly}>
        <label>System Prompt</label><textarea id="promptSystem" style="min-height:320px" ${readonly}>${escapeHtml(prompt.system_prompt)}</textarea>
        <label>User Template</label><textarea id="promptUserTemplate" style="min-height:90px" ${readonly}>${escapeHtml(prompt.user_template)}</textarea>
        <label>Sample input</label><textarea id="promptSample">The air conditioner in ARC room 205 is making loud noise and the room is too warm.</textarea>
        <label>Environment</label><select id="promptEnv">${envOptions()}</select>
        <div class="row"><button onclick="savePrompt(${prompt.id})" ${readonly}>Save</button><button class="secondary" onclick="createPromptDraft(${prompt.id})">Create Draft from This</button><button class="secondary" onclick="testPrompt(${prompt.id})">Test Draft</button><button class="secondary" onclick="runPromptTestCases(${prompt.id}, '${escapeAttr(prompt.endpoint)}')">Run Test Cases Against This Prompt</button><button class="secondary" onclick="runPromptSuites(${prompt.id}, '${escapeAttr(prompt.endpoint)}', true)">Run Required Test Suites Against This Prompt</button><button class="secondary" onclick="runPromptSuites(${prompt.id}, '${escapeAttr(prompt.endpoint)}', false)">Run All Test Suites Against This Prompt</button><button class="secondary" onclick="comparePromptAgainstActive(${prompt.id}, '${escapeAttr(prompt.endpoint)}')">Compare Against Active</button><button class="secondary" onclick="comparePromptAgainstAnother(${prompt.id}, '${escapeAttr(prompt.endpoint)}')">Compare Against Another Prompt</button><button class="danger" onclick="archivePrompt(${prompt.id})">Archive</button></div>
        <div class="ai-panel stack">
          <h3>Promotion Readiness</h3>
          <div class="muted">Activation requires a completed comparison against the current active prompt with no regressions or errors.</div>
          <label>Selected comparison</label><input id="promotionComparisonId" placeholder="cmp_..." value="">
          <label>Override reason</label><textarea id="promotionOverrideReason" placeholder="Required only for Override and Activate"></textarea>
          <div class="button-grid"><button class="secondary" onclick="checkPromotionGate(${prompt.id})">Check Promotion Gate</button><button onclick="activatePrompt(${prompt.id}, false)">Activate Prompt</button><button class="danger" onclick="activatePrompt(${prompt.id}, true)">Override and Activate</button></div>
          <div id="promotionGateResult" class="readiness warn"><strong>Gate status</strong><div class="muted">Select or enter a comparison id, then check readiness.</div></div>
        </div>
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Prompt test output</strong>${outputToolbar("promptResult")}</div><pre id="promptResult" style="min-height:160px">{}</pre></div>`;
    }

    async function savePrompt(id) {
      await api(`/api/admin/prompt-versions/${id}`, { method: "PATCH", body: JSON.stringify({ name: $("promptName").value, system_prompt: $("promptSystem").value, user_template: $("promptUserTemplate").value, model: $("promptModel").value, temperature: Number($("promptTemperature").value) }) });
      prompts();
    }

    async function createPromptDraft(id) {
      const existing = await api("/api/admin/prompt-versions");
      const selectedPrompt = existing.find(p => p.id === id);
      if (!selectedPrompt) return;
      const version = window.prompt("Draft version", `v${Date.now()}`);
      if (!version) return;
      await api("/api/admin/prompt-versions", { method: "POST", body: JSON.stringify({ endpoint: selectedPrompt.endpoint, version, name: `${selectedPrompt.name} draft`, status: "draft", system_prompt: selectedPrompt.system_prompt, user_template: selectedPrompt.user_template, model: selectedPrompt.model, temperature: selectedPrompt.temperature }) });
      prompts();
    }

    async function testPrompt(id) {
      const data = await api(`/api/admin/prompt-versions/${id}/test`, { method: "POST", body: JSON.stringify({ text: $("promptSample").value, environment_code: $("promptEnv").value }) });
      setConsoleOutput("promptResult", data);
    }

    async function runPromptTestCases(promptId, endpoint) {
      const data = await api("/api/admin/test-cases/run-batch", { method: "POST", body: JSON.stringify({ endpoint, enabled_only: true, prompt_id: promptId }) });
      setConsoleOutput("promptResult", data);
    }

    async function runPromptSuites(promptId, endpoint, requiredOnly) {
      const data = await api("/api/admin/test-suites/run-batch", { method: "POST", body: JSON.stringify({ endpoint, prompt_id: promptId, required_only: requiredOnly, enabled_only: true }) });
      setConsoleOutput("promptResult", data);
    }

    async function comparePromptAgainstActive(candidatePromptId, endpoint) {
      const prompts = await api(`/api/admin/prompt-versions/${endpoint}`);
      const active = prompts.find(p => p.status === "active");
      if (!active) { alert("No active prompt found for this endpoint."); return; }
      await runPromptComparison(active.id, candidatePromptId, endpoint);
    }

    async function comparePromptAgainstAnother(baselinePromptId, endpoint) {
      const other = window.prompt("Candidate prompt id");
      if (!other) return;
      await runPromptComparison(baselinePromptId, Number(other), endpoint);
    }

    async function runPromptComparison(baselinePromptId, candidatePromptId, endpoint) {
      const env = $("promptEnv")?.value || "";
      const data = await api("/api/admin/prompt-comparisons", { method: "POST", body: JSON.stringify({ endpoint, environment_code: env || null, baseline_prompt_id: baselinePromptId, candidate_prompt_id: candidatePromptId, enabled_only: true }) });
      setConsoleOutput("promptResult", data);
      await refreshPromptComparisons();
      renderPromptComparisonDetail(data);
    }

    async function refreshPromptComparisons() {
      if (!$("promptComparisons")) return;
      const comparisons = await api("/api/admin/prompt-comparisons?limit=25").catch(() => []);
      $("promptComparisons").innerHTML = renderPromptComparisonsTable(comparisons);
    }

    function renderPromptComparisonsTable(rows) {
      if (!rows.length) return '<p class="muted">No prompt comparisons yet.</p>';
      return `<table><thead><tr><th>Comparison</th><th>Endpoint</th><th>Environment</th><th>Baseline</th><th>Candidate</th><th>Total</th><th>Improved</th><th>Regressed</th><th>Status</th><th>Started</th><th>Actions</th></tr></thead><tbody>${rows.map(r => {
        const s = r.summary_json || {};
        return `<tr><td><strong>${escapeHtml(r.comparison_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td>${escapeHtml(r.baseline_version || String(r.baseline_prompt_id))}</td><td>${escapeHtml(r.candidate_version || String(r.candidate_prompt_id))}</td><td>${s.total ?? 0}</td><td>${s.improved ?? 0}</td><td>${s.regressed ?? 0}</td><td><span class="pill ${r.status === "completed" ? "ok" : r.status === "failed" ? "danger" : "warning"}">${escapeHtml(r.status)}</span></td><td>${escapeHtml(r.started_at || "")}</td><td><button class="secondary" onclick="viewPromptComparison('${escapeAttr(r.comparison_id)}')">View</button></td></tr>`;
      }).join("")}</tbody></table>`;
    }

    async function viewPromptComparison(comparisonId) {
      const data = await api(`/api/admin/prompt-comparisons/${comparisonId}`);
      renderPromptComparisonDetail(data);
    }

    function renderPromptComparisonDetail(data) {
      const target = $("promptComparisonDetail");
      if (!target) return;
      const summary = data.summary || data.summary_json || {};
      const cases = data.cases || [];
      target.innerHTML = `<div class="row" style="margin-bottom:10px"><button class="secondary" onclick="useComparisonForPromotion('${escapeAttr(data.comparison_id)}', ${Number(data.candidate_prompt_id || 0)})">Use This Comparison for Promotion</button><span class="muted">Candidate prompt #${escapeHtml(data.candidate_prompt_id || "")}</span></div><div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.total ?? 0}</div><div class="muted">Total</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.improved ?? 0}</div><div class="muted">Improved</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.regressed ?? 0}</div><div class="muted">Regressed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${summary.error ?? 0}</div><div class="muted">Errors</div></div></div>
      </div>
      <table><thead><tr><th>Test Case</th><th>Baseline</th><th>Candidate</th><th>Result</th><th>Duration</th><th>Actions</th></tr></thead><tbody>${cases.map(c => {
        const details = c.comparison_json || c;
        const baseline = details.baseline || {};
        const candidate = details.candidate || {};
        return `<tr><td>${escapeHtml(details.test_case_name || c.test_case_name || String(c.test_case_id))}</td><td><span class="pill ${baseline.status === "passed" || baseline.status === "warning" ? "ok" : "danger"}">${escapeHtml(baseline.status || c.baseline_status || "")}</span></td><td><span class="pill ${candidate.status === "passed" || candidate.status === "warning" ? "ok" : "danger"}">${escapeHtml(candidate.status || c.candidate_status || "")}</span></td><td><span class="pill ${details.result === "regressed" || details.result === "error" ? "danger" : details.result === "improved" ? "ok" : ""}">${escapeHtml(details.result || c.result || "")}</span></td><td>${baseline.duration_ms ?? ""} / ${candidate.duration_ms ?? ""} ms</td><td class="row">${baseline.run_id ? `<button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(baseline.run_id)}')">Baseline Trace</button>` : ""}${candidate.run_id ? `<button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(candidate.run_id)}')">Candidate Trace</button>` : ""}</td></tr>`;
      }).join("")}</tbody></table>`;
    }

    function useComparisonForPromotion(comparisonId, candidatePromptId) {
      if ($("promotionComparisonId")) {
        $("promotionComparisonId").value = comparisonId;
        checkPromotionGate(candidatePromptId);
      } else {
        alert(`Open candidate prompt #${candidatePromptId}, then use comparison ${comparisonId} for promotion.`);
      }
    }

    function renderGateResult(data) {
      const target = $("promotionGateResult");
      if (!target) return;
      const summary = data.summary || {};
      const suite = data.suite_readiness || {};
      target.className = `readiness ${data.allowed ? "" : "fail"}`;
      target.innerHTML = `<strong>${data.allowed ? "Gate passed" : data.gate_status === "overridden" ? "Gate overridden" : "Gate blocked"}</strong>
        <div class="muted">Comparison: ${escapeHtml(data.comparison_id || "")}</div>
        ${data.reasons?.length ? `<ul>${data.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : '<p class="muted">No blocking reasons.</p>'}
        <div class="result-grid">
          <div>Total: <strong>${summary.total ?? 0}</strong></div><div>Baseline passed: <strong>${summary.baseline_passed ?? 0}</strong></div><div>Candidate passed: <strong>${summary.candidate_passed ?? 0}</strong></div>
          <div>Improved: <strong>${summary.improved ?? 0}</strong></div><div>Regressed: <strong>${summary.regressed ?? 0}</strong></div><div>Error: <strong>${summary.error ?? 0}</strong></div>
        </div>
        <h3>Required Suite Readiness</h3>
        <div class="pill ${suite.required_suites_found ? (suite.required_suites_passed ? "ok" : "danger") : ""}">${suite.required_suites_found ? (suite.required_suites_passed ? "required suites passed" : "required suites blocked") : "no required suites"}</div>
        ${suite.suite_failures?.length ? `<ul>${suite.suite_failures.map(f => `<li>${escapeHtml(f.name || f.suite_id)}: ${escapeHtml(f.reason)}</li>`).join("")}</ul>` : '<p class="muted">No required suite failures.</p>'}`;
    }

    async function checkPromotionGate(id) {
      const comparisonId = $("promotionComparisonId")?.value || "";
      const data = await api(`/api/admin/prompt-versions/${id}/promotion-check`, { method: "POST", body: JSON.stringify({ comparison_id: comparisonId || null }) });
      renderGateResult(data);
      return data;
    }

    async function activatePrompt(id, override = false) {
      const body = { comparison_id: $("promotionComparisonId")?.value || null, override, override_reason: $("promotionOverrideReason")?.value || "" };
      try {
        const data = await api(`/api/admin/prompt-versions/${id}/activate`, { method: "POST", body: JSON.stringify(body) });
        renderGateResult(data.gate || { allowed: true, summary: {}, reasons: [], comparison_id: body.comparison_id });
        await refreshPromptPromotions();
        prompts();
      } catch (e) {
        const detail = e.data?.detail;
        renderGateResult(typeof detail === "object" ? detail : { allowed: false, gate_status: "blocked", reasons: [e.message], summary: {}, comparison_id: body.comparison_id });
      }
    }

    async function refreshPromptPromotions() {
      if (!$("promptPromotions")) return;
      const promotions = await api("/api/admin/prompt-promotions?limit=25").catch(() => []);
      $("promptPromotions").innerHTML = renderPromptPromotionsTable(promotions);
    }

    function renderPromptPromotionsTable(rows) {
      if (!rows.length) return '<p class="muted">No prompt promotions recorded yet.</p>';
      return `<table><thead><tr><th>Promotion</th><th>Endpoint</th><th>Previous</th><th>Promoted</th><th>Comparison</th><th>Gate</th><th>Override</th><th>By</th><th>At</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `<tr>
        <td><strong>${escapeHtml(r.promotion_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.previous_version || String(r.previous_prompt_id || ""))}</td><td>${escapeHtml(r.promoted_version || String(r.promoted_prompt_id))}</td><td>${escapeHtml(r.comparison_id || "")}</td>
        <td><span class="pill ${r.gate_status === "passed" ? "ok" : r.gate_status === "overridden" ? "warning" : "danger"}">${escapeHtml(r.gate_status)}</span></td><td>${r.override_used ? "Yes" : "No"}</td><td>${escapeHtml(r.promoted_by_username || "")}</td><td>${escapeHtml(r.promoted_at || "")}</td>
        <td><button class="secondary" onclick="viewPromptPromotion('${escapeAttr(r.promotion_id)}')">View</button></td>
      </tr>`).join("")}</tbody></table>`;
    }

    async function viewPromptPromotion(promotionId) {
      const data = await api(`/api/admin/prompt-promotions/${promotionId}`);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="promotionModal"><div class="modal" style="max-width:900px"><h2>Prompt Promotion</h2><div class="modal-body">
        <div class="ai-panel ai-panel-dark"><div class="status-line"><strong>Promotion JSON</strong>${outputToolbar("promotionOut")}</div><pre id="promotionOut" style="min-height:320px"></pre></div>
      </div><div class="modal-actions"><button class="secondary" onclick="$('promotionModal').remove()">Close</button></div></div></div>`);
      setConsoleOutput("promotionOut", data);
    }

    async function archivePrompt(id) {
      if (!confirm("Archive this prompt version?")) return;
      await api(`/api/admin/prompt-versions/${id}/archive`, { method: "POST" });
      prompts();
    }

    async function keys() {
      const data = await api("/api/admin/api-keys");
      pageShell("API Keys", `<div class="grid">
        <div class="card span-4"><h2>Generate key</h2><div class="card-body stack"><label>Name</label><input id="kName" value="external-tester"><button onclick="createKey()">Generate</button></div></div>
        <div class="card span-8"><h2>Keys</h2><div class="card-body">${table(data, ["key_id","name","enabled","usage_count","last_used_at"], "disableKey")}</div></div>
        <div class="card span-12"><h2>Generated key output</h2><pre id="kOut">{}</pre></div>
      </div>`);
    }
    async function createKey() { const data = await api("/api/admin/api-keys", { method: "POST", body: JSON.stringify({ name: $("kName").value }) }); $("kOut").textContent = JSON.stringify(data, null, 2); }
    async function disableKey(id) { await api(`/api/admin/api-keys/${id}`, { method: "PATCH", body: JSON.stringify({ enabled: false }) }); keys(); }
    async function users() {
      const data = await api("/api/admin/users");
      pageShell("Users", `<div class="grid">
        <div class="card span-4"><h2>Create user</h2><div class="card-body stack"><label>Username</label><input id="uName"><label>Password</label><input id="uPass" type="password"><label>Role</label><select id="uRole"><option>user</option><option>admin</option></select><button onclick="createUser()">Create</button></div></div>
        <div class="card span-8"><h2>Users</h2><div class="card-body">${table(data, ["user_id","username","role","enabled","last_login_at"])}</div></div>
      </div>`);
    }
    async function createUser() { await api("/api/admin/users", { method: "POST", body: JSON.stringify({ username: $("uName").value, password: $("uPass").value, role: $("uRole").value }) }); users(); }
    async function logs() {
      const data = await api("/api/admin/logs?lines=220");
      const runs = await api("/api/admin/workflow-runs?limit=25").catch(() => []);
      pageShell("Logs", `<div class="grid">
        <div class="card span-12"><h2>Workflow Runs</h2><div class="card-body">${renderWorkflowRunsTable(runs)}</div></div>
        <div class="card span-12"><h2>Trace Detail</h2><div class="card-body" id="logTraceDetail"><span class="muted">Select View Trace from a workflow run.</span></div></div>
        <div class="card span-12"><h2>Runtime log</h2><pre>${data.lines.join("\n")}</pre></div>
      </div>`);
    }

    function renderWorkflowRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No workflow runs recorded yet.</p>';
      return `<table><thead><tr><th>Run ID</th><th>Endpoint</th><th>Environment</th><th>Status</th><th>Duration</th><th>Started</th><th>Source</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr><td><strong>${escapeHtml(r.run_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td><span class="pill ${r.status === "failed" ? "danger" : r.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(r.status)}</span></td><td>${r.duration_ms ?? ""} ms</td><td>${escapeHtml(r.started_at || "")}</td><td>${escapeHtml(r.source || "")}</td><td><button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(r.run_id)}')">View Trace</button></td></tr>`).join("")}</tbody></table>`;
    }

    async function viewWorkflowTrace(runId) {
      const trace = await api(`/api/admin/workflow-runs/${runId}`);
      $("logTraceDetail").innerHTML = renderWorkflowTrace(trace);
    }
    async function reports() { const data = await api("/api/admin/reports/usage"); pageShell("Reports", `<div class="card"><h2>Usage</h2><div class="card-body">${table(data, ["endpoint","status_code","key_name","environment_code","calls","avg_duration_ms"])}</div></div>`); }
    async function kb() { const data = await api("/api/kb/status"); pageShell("Knowledge Base", `<div class="card"><h2>Future KB interface</h2><div class="card-body"><pre>${JSON.stringify(data, null, 2)}</pre></div></div>`); }
    async function remote() { const data = await api("/api/admin/settings/remote_access_url").catch(()=>({ value:"" })); pageShell("Remote Access", `<div class="card"><h2>Remote link notes</h2><div class="card-body stack"><input id="remoteUrl" value="${data.value||""}" placeholder="https://example.trycloudflare.com"><button onclick="saveRemote()">Save</button><p class="muted">Cloudflare is still started manually. Store the URL here for reference.</p></div></div>`); }
    async function saveRemote() { await api("/api/admin/settings/remote_access_url", { method: "PATCH", body: JSON.stringify({ value: $("remoteUrl").value }) }); remote(); }
    async function system() {
      const s = await api("/api/system/status");
      pageShell("System", `<div class="grid"><div class="card span-6"><h2>Status</h2><div class="card-body"><pre>${JSON.stringify(s, null, 2)}</pre></div></div>
      <div class="card span-6"><h2>Local-only controls</h2><div class="card-body row"><button onclick="api('/api/system/ollama/start',{method:'POST'}).then(system)">Start Ollama</button><button class="secondary" onclick="api('/api/system/ollama/stop',{method:'POST'}).then(system)">Stop Ollama</button><button class="danger" onclick="api('/api/system/shutdown',{method:'POST'})">Stop API</button></div></div></div>`);
    }
    function table(rows, cols, action) {
      if (!rows || !rows.length) return "<p class='muted'>No records.</p>";
      return `<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join("")}${action?"<th>Action</th>":""}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${r[c] ?? ""}</td>`).join("")}${action?`<td><button class="danger" onclick="${action}('${r.key_id}')">Disable</button></td>`:""}</tr>`).join("")}</tbody></table>`;
    }
    boot();
  </script>
</body>
</html>"""



def render_portal_html() -> str:
    return PORTAL_HTML
