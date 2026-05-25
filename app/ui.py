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
    .metadata-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 8px; }
    .metadata-item { border: 1px solid var(--replicate-line); background: #f8fafc; padding: 8px; min-width: 0; }
    .metadata-item label { margin-bottom: 4px; }
    .metadata-value { overflow-wrap: anywhere; }
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
    .login-docs-link {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid #eef0f3;
    }
    .docs-public {
      display: none;
      min-height: 100vh;
      background: #f7f7f8;
      padding: 34px clamp(18px, 4vw, 48px);
    }
    .docs-shell {
      width: min(1080px, 100%);
      margin: 0 auto;
      display: grid;
      gap: 18px;
    }
    .docs-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      padding: 6px 0 10px;
    }
    .docs-top h1 {
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: -.02em;
    }
    .docs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }
    .docs-card {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      box-shadow: var(--shadow-sm);
      padding: 18px;
    }
    .docs-card h2 { margin: 0 0 8px; font-size: 16px; letter-spacing: -.01em; }
    .docs-card p { margin: 0; line-height: 1.5; }
    .docs-card ul { margin: 14px 0 0; padding-left: 18px; color: #475569; line-height: 1.5; }
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
    .nav-group { display: grid; gap: 2px; margin-bottom: 16px; }
    .nav-group-title {
      padding: 10px 11px 5px;
      color: #94a3b8;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .section-stack { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 18px; }
    .dashboard-hero {
      display: grid;
      width: 100%;
      grid-column: 1 / -1;
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
    .credentials-panel {
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #fbfcfe;
      padding: 10px 12px;
    }
    .credentials-panel summary {
      cursor: pointer;
      font-weight: 700;
      color: #334155;
      list-style: none;
    }
    .credentials-panel summary::-webkit-details-marker { display: none; }
    .credentials-panel .compact-field-row { margin-top: 10px; }
    .mobile-menu-toggle { display: none; }
    .admin-badge {
      margin-left: auto;
      border: 1px solid #fee2e2;
      border-radius: 999px;
      background: #fff7f7;
      color: #b91c1c;
      padding: 1px 6px;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .02em;
    }
    .nav button.admin-only::after { content: none; }
    .coming-soon-tabs {
      margin-top: 10px;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #fbfcfe;
      padding: 10px 12px;
    }
    .coming-soon-tabs summary {
      cursor: pointer;
      font-weight: 700;
      color: #475569;
      list-style: none;
    }
    .coming-soon-tabs summary::-webkit-details-marker { display: none; }
    .coming-soon-tabs .tabs { margin-top: 10px; }
    .quiet-toolbar {
      border-style: dashed;
      background: #fbfcfe;
      box-shadow: none;
    }
    .input-with-voice {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: start;
    }
    .voice-icon-button {
      width: 42px;
      min-width: 42px;
      height: 42px;
      padding: 0;
      border-radius: 999px;
      font-size: 18px;
      line-height: 1;
    }
    .voice-icon-button.listening {
      background: #dc2626;
      box-shadow: 0 0 0 4px rgba(220, 38, 38, .14);
    }
    .voice-settings {
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #fbfcfe;
      padding: 10px 12px;
    }
    .voice-settings summary {
      cursor: pointer;
      font-weight: 700;
      color: #334155;
      list-style: none;
    }
    .voice-settings summary::-webkit-details-marker { display: none; }
    .voice-settings-body { margin-top: 10px; }
    .table-scroll {
      width: 100%;
      overflow-x: auto;
    }
    .table-scroll table { min-width: 720px; }
    select, .cmms-select {
      appearance: none;
      min-height: 42px;
      border-radius: 12px;
      padding: 9px 38px 9px 13px;
      background: linear-gradient(180deg, #ffffff, #f8fafc);
      background-image: none;
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
    .grid { gap: 14px; }
    .card-body { padding: 16px; }
    .run-surface { gap: 8px; padding: 10px; }
    .compact-field-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: end;
    }
    .compact-field-row-two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .compact-field-row label { margin-top: 6px; }
    .compact-field-row button { white-space: nowrap; min-height: 36px; padding: 7px 11px; }
    .compact-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 6px; }
    .compact-actions button { min-height: 34px; padding: 6px 10px; }
    .test-console-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .compact-textarea { min-height: 96px; }
    .test-console-textarea { min-height: 180px; }
    .orchestration-textarea { min-height: 180px; }
    .email-compose textarea.compact-textarea { min-height: 180px; }
    .console-output { max-height: min(42vh, 420px); overflow: auto; }
    .collapsible-panel {
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #fff;
      box-shadow: var(--shadow-sm);
      overflow: hidden;
    }
    .collapsible-panel summary {
      cursor: pointer;
      list-style: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 9px 11px;
      font-weight: 700;
      font-size: 13px;
    }
    .collapsible-panel summary::-webkit-details-marker { display: none; }
    .collapsible-panel summary::before {
      content: ">";
      color: #6b7280;
      font-size: 12px;
      margin-right: 2px;
      transition: transform .14s ease;
    }
    .collapsible-panel[open] summary::before { transform: rotate(90deg); }
    .collapsible-panel summary > span { flex: 1; }
    .collapsible-content { border-top: 1px solid #eef0f3; padding: 10px 11px; }
    .collapsible-content .ai-panel, .collapsible-content .readiness { box-shadow: none; }
    .collapsible-dark {
      background: #0f172a;
      color: #f8fafc;
      border-color: #111827;
      box-shadow: 0 10px 24px rgba(15, 23, 42, .16);
    }
    .collapsible-dark summary::before { color: #cbd5e1; }
    .collapsible-dark .collapsible-content { border-top-color: rgba(148, 163, 184, .2); }
    .collapsible-dark pre { background: transparent; color: #f8fafc; padding: 0; min-height: 180px; }
    .collapsible-toolbar { justify-content: flex-end; margin-bottom: 8px; }
    @media (max-width: 1200px) { .contracts-layout { grid-template-columns: 1fr; } }
    @media (max-width: 900px) {
      .app { grid-template-columns: 1fr; grid-template-rows: auto auto 1fr; }
      .top { min-height: 56px; gap: 10px; flex-wrap: wrap; align-content: center; }
      .brand { max-width: 160px; line-height: 1.2; }
      .userbar { margin-left: auto; gap: 8px; }
      .userbar span { max-width: 72px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .mobile-menu-toggle { display: inline-flex; align-items: center; justify-content: center; min-height: 32px; padding: 6px 11px; }
      .nav { display: none; grid-column: 1 / -1; max-height: calc(100vh - 56px); overflow: auto; border-right: 0; border-bottom: 1px solid #e5e7eb; }
      .app.nav-open .nav { display: block; }
      .nav-group { display: grid; margin-bottom: 12px; }
      .nav-group-title { display: block; }
      .nav button { min-width: 0; }
      .content { padding: 24px 22px; }
      .docs-public { padding: 24px 18px; }
      .docs-top { display: grid; }
      .dashboard-hero { grid-template-columns: 1fr; }
      .page-title { display: grid; }
      .tabs { overflow-x: auto; white-space: nowrap; }
      .span-3,.span-4,.span-5,.span-6,.span-7,.span-8 { grid-column: span 12; }
      .result-grid, .compact-field-row, .compact-field-row-two { grid-template-columns: 1fr; }
    }
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
      <div class="login-docs-link"><button class="secondary" onclick="showPublicDocs()">Browse documentation</button></div>
    </div>
  </div>
  <div id="docsView" class="docs-public">
    <div class="docs-shell">
      <div class="docs-top">
        <div>
          <h1>Documentation</h1>
          <p class="muted">Read-only product notes for visitors. Browsing docs does not grant a portal session or API access.</p>
        </div>
        <button class="secondary" onclick="showLogin()">Sign in</button>
      </div>
      <div id="publicDocs" class="docs-grid">
        <div class="docs-card"><p class="muted">Loading documentation...</p></div>
      </div>
    </div>
  </div>
  <div id="appView" class="app">
    <header class="top">
      <div class="brand">CMMS LLM Management Portal</div>
      <div class="userbar"><button class="secondary mobile-menu-toggle" onclick="toggleNav()">Menu</button><span id="healthText">Checking...</span><span id="userText"></span><button class="secondary" onclick="logout()">Logout</button></div>
    </header>
    <nav class="nav" id="nav"></nav>
    <main class="content">
      <div class="page-title"><div class="page-title-main"><h1 id="pageTitle">Dashboard</h1><div id="pageSubtitle" class="page-subtitle"></div></div><div id="pageActions"></div></div>
      <div id="page"></div>
    </main>
  </div>
  <script>
    const state = {
      me: null, page: "dashboard", envs: [], keys: [], output: {}, selectedEnv: "DEFAULT", defaultApiKey: "",
      envTab: "codes", selectedCategory: "buildings", selectedCode: null, codeData: null, validationRules: [], cmmsConnector: null, cmmsPushEvents: [],
      inputMode: "text", recognition: null, voiceSupported: null, voiceBaseTranscript: "", voiceFinalTranscript: "",
      voiceStopping: false, voiceStatus: "Idle", voiceSilenceTimer: null, outputs: {},
      lastTestResponse: null, lastTestInput: null, metadataReviewExtracted: null, selectedTestCaseId: null,
      reviewerPromptComparison: null, systemControlKey: "", setupStatus: null, backups: []
    };
    const menu = [
      ["orchestration","Orchestration",false,"O"],
      ["dashboard","Dashboard",false,"▦"],["test","Test Console",false,"▶"],["email","Email Intake",false,"✉"],["builder","API Builder",false,"⌘"],["testCases","Test Cases",true,"✓"],["testSuites","Test Suites",true,"✓"],
      ["environments","Environments",true,"◇"],["contracts","Output Contracts",true,"▣"],["prompts","Prompt Versions",true,"✎"],["keys","API Keys",true,"◆"],
      ["users","Users",true,"◉"],["logs","Logs",false,"☰"],["reports","Reports",false,"↗"],["kb","Knowledge Base",false,"◌"],
      ["remote","Remote Access",true,"⇄"],["system","System",true,"⚙"],["setup","Setup Wizard",true,"S"]
    ];
    const menuGroups = [
      ["Operate", ["dashboard", "orchestration", "test", "email", "builder"]],
      ["Configure", ["environments", "contracts", "prompts", "keys"]],
      ["Quality", ["testCases", "testSuites", "logs", "reports", "kb"]],
      ["Admin", ["users", "remote", "system", "setup"]]
    ];
    const menuById = Object.fromEntries(menu.map(item => [item[0], item]));
    const codeCategories = [
      ["buildings","Buildings"],["rooms","Rooms"],["priorities","Priorities"],["work_order_types","Work order types"],
      ["assign_to","Assign to"],["issue_to_employee_number","Issue to employee #"],["job_type","Job type"],
      ["assets","Assets"],["technician_roster","Technician roster"],["custom:inventory_parts","Inventory parts"],["custom:future","Custom future"]
    ];
    const $ = (id) => document.getElementById(id);
    const OPERATOR_API_KEY_STORAGE_KEY = "cmmsOperatorApiKey";
    function loadSavedApiKey() {
      try { state.defaultApiKey = localStorage.getItem(OPERATOR_API_KEY_STORAGE_KEY) || ""; }
      catch { state.defaultApiKey = ""; }
    }
    function rememberApiKey(value) {
      const key = String(value || "").trim();
      state.defaultApiKey = key;
      try {
        if (key) localStorage.setItem(OPERATOR_API_KEY_STORAGE_KEY, key);
        else localStorage.removeItem(OPERATOR_API_KEY_STORAGE_KEY);
      } catch {}
    }
    function forgetApiKey() {
      state.defaultApiKey = "";
      try { localStorage.removeItem(OPERATOR_API_KEY_STORAGE_KEY); } catch {}
      ["tKey", "eKey", "bKey"].forEach(id => { if ($(id)) $(id).value = ""; });
      if ($("bOut")) buildCall();
    }
    function collapsiblePanel(title, body, options = {}) {
      const open = options.open ? " open" : "";
      const dark = options.dark ? " collapsible-dark" : "";
      return `<details class="collapsible-panel${dark}"${open}><summary><span>${escapeHtml(title)}</span></summary><div class="collapsible-content">${body}</div></details>`;
    }
    function tableScroll(html) { return `<div class="table-scroll">${html}</div>`; }
    async function api(path, opts = {}) {
      const res = await fetch(path, { credentials: "same-origin", ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
      if (!res.ok) throw Object.assign(new Error(data.detail || "Request failed"), { data, status: res.status });
      return data;
    }
    function showLogin() {
      $("docsView").style.display = "none";
      $("appView").style.display = "none";
      $("loginView").style.display = "grid";
    }
    async function showPublicDocs() {
      $("loginView").style.display = "none";
      $("appView").style.display = "none";
      $("docsView").style.display = "block";
      await loadPublicDocs();
    }
    async function loadPublicDocs() {
      const target = $("publicDocs");
      target.innerHTML = `<div class="docs-card"><p class="muted">Loading documentation...</p></div>`;
      try {
        const docs = await api("/api/public/documentation");
        target.innerHTML = docs.map(renderPublicDoc).join("");
      } catch (e) {
        target.innerHTML = `<div class="docs-card"><h2>Documentation unavailable</h2><p class="muted">${escapeHtml(e.message)}</p></div>`;
      }
    }
    function renderPublicDoc(doc) {
      const sections = (doc.sections || []).map(item => `<li>${escapeHtml(item)}</li>`).join("");
      return `<article class="docs-card"><h2>${escapeHtml(doc.title)}</h2><p class="muted">${escapeHtml(doc.summary)}</p>${sections ? `<ul>${sections}</ul>` : ""}</article>`;
    }
    function registerOfflineShell() {
      if (!("serviceWorker" in navigator)) return;
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/offline-sw.js").catch(() => {});
      });
    }
    async function login() {
      try {
        await api("/auth/login", { method: "POST", body: JSON.stringify({ username: $("loginUser").value, password: $("loginPass").value }) });
        await boot();
      } catch (e) { $("loginMsg").textContent = e.message; }
    }
    async function logout() { await api("/auth/logout", { method: "POST" }).catch(() => {}); location.reload(); }
    async function boot() {
      loadSavedApiKey();
      try {
        state.me = await api("/api/me");
        $("loginView").style.display = "none"; $("docsView").style.display = "none"; $("appView").style.display = "grid";
        $("userText").textContent = `${state.me.username} (${state.me.role})`;
        renderNav(); await refreshBase(); show("dashboard");
      } catch { showLogin(); }
    }
    async function refreshBase() {
      state.envs = await api("/api/environments").catch(() => []);
      state.keys = state.me?.role === "admin" ? await api("/api/admin/api-keys").catch(() => []) : [];
      const health = await api("/health").catch(() => null);
      $("healthText").textContent = health ? "Local API online" : "API offline";
    }
    function renderNav() {
      $("nav").innerHTML = menuGroups.map(([group, ids]) => {
        const items = ids.map(id => menuById[id]).filter(Boolean).filter(([, , admin]) => !admin || state.me?.role === "admin");
        if (!items.length) return "";
        return `<div class="nav-group"><div class="nav-group-title">${group}</div>${items.map(([id,label,admin,icon]) =>
          `<button class="${state.page===id?'active':''} ${admin?'admin-only':''}" onclick="show('${id}')"><span class="cmms-nav-icon">${icon}</span><span>${label}</span>${admin ? '<span class="admin-badge">Admin</span>' : ''}</button>`
        ).join("")}</div>`;
      }).join("");
    }
    function toggleNav() { $("appView").classList.toggle("nav-open"); }
    function pageShell(title, html, actions = "", subtitle = "") {
      $("pageTitle").textContent = title;
      $("pageActions").innerHTML = actions;
      const subtitleEl = $("pageSubtitle");
      if (subtitleEl) subtitleEl.textContent = subtitle;
      $("page").innerHTML = html;
      $("appView").classList.remove("nav-open");
      renderNav();
    }
    function envOptions() {
      const selectedEnv = state.envs.some(e => e.environment_code === "DEFAULT") ? "DEFAULT" : state.envs[0]?.environment_code;
      return state.envs.map(e => `<option value="${e.environment_code}" data-workflow-mode="${workflowModeForEnvironment(e)}" ${e.environment_code === selectedEnv ? "selected" : ""}>${e.environment_code} - ${e.name}</option>`).join("");
    }
    function workflowModeForEnvironment(env) {
      return env?.default_workflow_mode === "full" ? "full" : "fast";
    }
    function selectedEnvironmentWorkflowMode(envSelectId) {
      const option = $(envSelectId)?.selectedOptions?.[0];
      return option?.dataset?.workflowMode === "full" ? "full" : "fast";
    }
    function syncWorkflowModeFromEnvironment(envSelectId, workflowSelectId) {
      const workflow = $(workflowSelectId);
      if (workflow) workflow.value = selectedEnvironmentWorkflowMode(envSelectId);
    }
    function show(id) {
      state.page = id; renderNav();
      const handlers = { dashboard, orchestration, test, email: emailIntake, builder, testCases, testSuites, environments, contracts, prompts, keys, users, logs, reports, kb, remote, system, setup: setupWizard };
      handlers[id]();
    }
    async function dashboard() {
      pageShell("Dashboard", `<div class="section-stack">
        <div class="dashboard-hero">
          <div class="card"><h2>Control plane readiness</h2><div class="card-body"><div class="metric">${state.envs.length} environments</div><p class="muted">Local advisory workflow with deterministic validation gates.</p></div></div>
          <div class="card"><h2>System status</h2><div class="card-body dashboard-status-list">
            <div class="status-row"><span>API keys</span><strong>${state.keys.length}</strong></div>
            <div class="status-row"><span>Current role</span><strong>${state.me.role}</strong></div>
            <div class="status-row"><span>Model runtime</span><strong>Local</strong></div>
          </div></div>
        </div>
        <div class="card span-12"><h2>Safety posture</h2><div class="card-body">Advisory mode only. No CMMS write-back, work order creation, approval, or email sending occurs.</div></div>
        <div class="card span-12"><h2>Regression Health</h2><div class="card-body" id="regressionDashboard"><p class="muted">Loading regression dashboard...</p></div></div>
      </div>`, "", "Overview first; detailed checks stay grouped below.");
      const data = await api("/api/admin/regression-dashboard").catch(e => ({ error: e.message }));
      renderRegressionDashboard(data);
    }

    function orchestration() {
      pageShell("Orchestration", `<div class="grid">
        <div class="card playground span-4"><div class="playground-header"><div><div class="playground-title">Instruction</div><div class="playground-subtitle">cmms-intake orchestration_summary</div></div><span class="pill">dry-run</span></div><div class="card-body stack">
          <details class="credentials-panel"><summary>Test API credentials</summary><div class="compact-field-row"><div><label>API key</label><input id="oKey" type="password" value="${escapeAttr(state.defaultApiKey)}" placeholder="Paste generated API key" oninput="rememberApiKey(this.value)"></div><button class="secondary" onclick="forgetApiKey()">Forget key</button></div></details>
          <div class="compact-field-row compact-field-row-two"><div><label>Environment</label><select id="oEnv" onchange="syncWorkflowModeFromEnvironment('oEnv', 'oWorkflowMode')">${envOptions()}</select></div><div><label>Workflow</label><select id="oWorkflowMode"><option value="fast" selected>Fast</option><option value="full">Full</option></select></div></div>
          <label>Request</label><textarea id="oText" class="compact-textarea orchestration-textarea">Create a high priority work order for AHU-3, assign it to tonight's on-duty technician, check filter inventory, and create a purchase request if none are available.</textarea>
          <div class="compact-actions"><button id="oRunBtn" onclick="runOrchestration()">Run Orchestration</button><button class="secondary" onclick="setOrchestrationExample()">Reset Example</button></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Execution Plan</div><div class="playground-subtitle" id="oRunLabel">No run yet</div></div><span id="oStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="orchestrationSummary" class="readiness"><strong>Orchestration summary</strong><div class="muted">Run a request to view the end-to-end plan.</div></div>
            <div class="result-grid">
              ${collapsiblePanel("Actions", `<div id="orchestrationActions"><span class="muted">No actions yet.</span></div>`, { open: true })}
              ${collapsiblePanel("Inventory + Procurement", `<div id="orchestrationProcurement"><span class="muted">No inventory check yet.</span></div>`, { open: true })}
            </div>
            ${collapsiblePanel("Raw response", `<div class="status-line collapsible-toolbar">${outputToolbar("orchestrationOut")}</div><pre id="orchestrationOut">{}</pre>`, { dark: true })}
          </div>
        </div>
      </div>`, "", "Focused view for one natural-language instruction and its deterministic multi-action plan.");
      syncWorkflowModeFromEnvironment('oEnv', 'oWorkflowMode');
    }

    function setOrchestrationExample() {
      if ($("oText")) $("oText").value = "Create a high priority work order for AHU-3, assign it to tonight's on-duty technician, check filter inventory, and create a purchase request if none are available.";
    }

    async function runOrchestration() {
      const key = $("oKey")?.value || state.defaultApiKey || "";
      rememberApiKey(key);
      const payload = {
        text: $("oText").value,
        environment_code: $("oEnv").value,
        workflow_mode: $("oWorkflowMode").value
      };
      if ($("oStatus")) { $("oStatus").textContent = "Running"; $("oStatus").className = "pill warning"; }
      try {
        const data = await api("/api/ai/cmms-intake", { method: "POST", headers: { "x-api-key": state.defaultApiKey }, body: JSON.stringify(payload) });
        state.lastTestResponse = data;
        if ($("oRunLabel")) $("oRunLabel").textContent = `Run ${data.run_id || ""}`;
        renderOrchestrationSummary(data);
        renderOrchestrationActions(data);
        setConsoleOutput("orchestrationOut", data);
        if ($("oStatus")) {
          const status = data.orchestration_summary?.status || "completed";
          $("oStatus").textContent = status;
          $("oStatus").className = `pill ${status === "dry_run" || status === "needs_review" ? "warning" : status === "failed" || status === "blocked" ? "danger" : "ok"}`;
        }
      } catch (e) {
        if ($("oStatus")) { $("oStatus").textContent = "Failed"; $("oStatus").className = "pill danger"; }
        if ($("orchestrationSummary")) $("orchestrationSummary").innerHTML = `<strong>Run failed</strong><div class="muted">${escapeHtml(e.message)}</div>`;
      }
    }

    function renderOrchestrationSummary(data) {
      const summary = data.orchestration_summary || {};
      if (!$("orchestrationSummary")) return;
      if (!summary.schema) {
        $("orchestrationSummary").innerHTML = '<strong>No orchestration summary</strong><div class="muted">Response did not include orchestration_summary.</div>';
        return;
      }
      const steps = summary.steps || {};
      $("orchestrationSummary").className = `readiness ${summary.status === "blocked" || summary.status === "failed" ? "fail" : summary.status === "needs_review" || summary.status === "dry_run" ? "warn" : ""}`;
      $("orchestrationSummary").innerHTML = `<strong>${escapeHtml(summary.operator_message || "Orchestration summary")}</strong>
        <div class="metadata-grid" style="margin-top:10px">
          <div class="metadata-item"><label>Status</label><div class="metadata-value">${escapeHtml(summary.status || "")}</div></div>
          <div class="metadata-item"><label>Asset</label><div class="metadata-value">${escapeHtml(summary.asset_code || "")}</div></div>
          <div class="metadata-item"><label>Priority</label><div class="metadata-value">${escapeHtml(summary.priority || "")}</div></div>
          <div class="metadata-item"><label>Technician</label><div class="metadata-value">${escapeHtml(steps.assignment?.technician || "")}</div></div>
          <div class="metadata-item"><label>Inventory</label><div class="metadata-value">${escapeHtml(steps.inventory?.status || "")}</div></div>
          <div class="metadata-item"><label>Procurement</label><div class="metadata-value">${escapeHtml(steps.procurement?.status || "")}</div></div>
        </div>`;
    }

    function renderOrchestrationActions(data) {
      const summary = data.orchestration_summary || {};
      const actions = data.action_plan?.actions || data.result?.action_plan?.actions || [];
      const procurement = data.procurement_request || data.result?.procurement_request || {};
      if ($("orchestrationActions")) {
        $("orchestrationActions").innerHTML = actions.length ? `<table><thead><tr><th>Action</th><th>Status</th><th>Method</th><th>Review</th></tr></thead><tbody>${actions.map(action => `<tr><td>${escapeHtml(action.action_id || "")}</td><td>${escapeHtml(action.status || "")}</td><td>${escapeHtml(action.method || action.type || "")}</td><td>${action.requires_review ? "Yes" : "No"}</td></tr>`).join("")}</tbody></table>` : '<span class="muted">No actions returned.</span>';
      }
      if ($("orchestrationProcurement")) {
        const shortages = summary.steps?.inventory?.shortage_items || [];
        $("orchestrationProcurement").innerHTML = `<div class="stack">
          <div><strong>Inventory:</strong> ${escapeHtml(summary.steps?.inventory?.status || "")}</div>
          <div><strong>Purchase request:</strong> ${escapeHtml(summary.steps?.procurement?.status || procurement.status || "")}</div>
          <div class="muted">${escapeHtml(summary.steps?.procurement?.reason || procurement.reason || "")}</div>
          ${shortages.length ? `<table><thead><tr><th>Part</th><th>On Hand</th><th>Shortage</th></tr></thead><tbody>${shortages.map(item => `<tr><td>${escapeHtml(item.part_number || "")}</td><td>${item.quantity_on_hand ?? ""}</td><td>${item.shortage_quantity ?? ""}</td></tr>`).join("")}</tbody></table>` : ""}
          ${actions.some(action => action.action_id === "create_purchase_request") ? '<span class="pill warning">create_purchase_request</span>' : ""}
        </div>`;
      }
    }

    function renderRegressionDashboard(data) {
      if (!$("regressionDashboard")) return;
      if (data.error) { $("regressionDashboard").innerHTML = `<span class="pill danger">Dashboard unavailable</span><p>${escapeHtml(data.error)}</p>`; return; }
      const readiness = data.required_suite_readiness || {};
      const workflow = data.workflow_summary || {};
      const pushGate = data.cmms_push_gate_summary || {};
      $("regressionDashboard").innerHTML = `<div class="grid">
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.passed ?? 0}/${readiness.total ?? 0}</div><div class="muted">Required suites passed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.failed ?? 0}</div><div class="muted">Required suites failed</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${readiness.not_run ?? 0}</div><div class="muted">Required suites not run</div></div></div>
        <div class="card span-3"><div class="card-body"><div class="metric">${workflow.failed ?? 0}</div><div class="muted">Recent workflow failures</div></div></div>
        <div class="card span-4"><h2>Workflow Summary</h2><div class="card-body">${renderWorkflowSummary(workflow)}</div></div>
        <div class="card span-4"><h2>CMMS Push Gate</h2><div class="card-body">${renderCmmsPushGateSummary(pushGate)}</div></div>
        <div class="card span-4"><h2>Top Failing Fields</h2><div class="card-body">${renderFailingFields(data.top_failing_fields || [])}</div></div>
        <div class="card span-12"><h2>Recent Validation Failures</h2><div class="card-body">${renderValidationFailures(data.recent_validation_failures || [])}</div></div>
        <div class="span-12 dashboard-regression-details">${collapsiblePanel("Regression details", `<div class="grid">
          <div class="card span-12"><h2>Required Suite Readiness</h2><div class="card-body">${tableScroll(renderRequiredSuiteReadiness(readiness.items || []))}</div></div>
          <div class="card span-12"><h2>Latest Suite Runs</h2><div class="card-body">${tableScroll(renderDashboardSuiteRuns(data.latest_suite_runs || []))}</div></div>
          <div class="card span-6"><h2>Recent Prompt Comparisons</h2><div class="card-body">${tableScroll(renderDashboardComparisons(data.recent_prompt_comparisons || []))}</div></div>
          <div class="card span-6"><h2>Recent Promotions</h2><div class="card-body">${tableScroll(renderDashboardPromotions(data.recent_promotions || []))}</div></div>
        </div>`)}</div>
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

    function renderCmmsPushGateSummary(summary) {
      const ready = summary.recent_ready_runs || [];
      const blocked = summary.recent_blocked_runs || [];
      return `<div class="stack">
        <div class="metadata-grid">
          <div class="metadata-item"><label>Push-ready</label><div class="metadata-value"><strong>${summary.ready_count ?? 0}</strong></div></div>
          <div class="metadata-item"><label>Blocked</label><div class="metadata-value"><strong>${summary.blocked_count ?? 0}</strong></div></div>
          <div class="metadata-item"><label>Sent</label><div class="metadata-value"><strong>${summary.sent_count ?? 0}</strong></div></div>
          <div class="metadata-item"><label>Dry run</label><div class="metadata-value"><strong>${summary.dry_run_count ?? 0}</strong></div></div>
        </div>
        <div><strong>Recent ready</strong>${ready.length ? `<table><tbody>${ready.slice(0, 3).map(r => `<tr><td>${escapeHtml(r.run_id)}</td><td>${statusPill(r.status)}</td><td><button class="secondary" onclick="show('logs'); setTimeout(()=>viewWorkflowTrace('${escapeAttr(r.run_id)}'), 100)">View Run</button></td></tr>`).join("")}</tbody></table>` : '<p class="muted">No push-ready runs.</p>'}</div>
        <div><strong>Recent blocked</strong>${blocked.length ? `<table><tbody>${blocked.slice(0, 3).map(r => `<tr><td>${escapeHtml(r.run_id)}</td><td>${escapeHtml((r.blocked_reasons || []).join(", "))}</td><td><button class="secondary" onclick="show('logs'); setTimeout(()=>viewWorkflowTrace('${escapeAttr(r.run_id)}'), 100)">View Run</button></td></tr>`).join("")}</tbody></table>` : '<p class="muted">No blocked push gates.</p>'}</div>
      </div>`;
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
          <details class="credentials-panel"><summary>Test API credentials</summary><div class="compact-field-row"><div><label>API key</label><input id="tKey" type="password" value="${escapeAttr(state.defaultApiKey)}" placeholder="Paste generated API key" oninput="rememberApiKey(this.value)"></div><button class="secondary" onclick="forgetApiKey()">Forget key</button></div></details>
          <div class="compact-field-row compact-field-row-two"><div><label>Mode</label><div class="select-wrap"><select id="tEndpoint" class="cmms-select" onchange="updateTestModeUi(); renderTestModeHelp()"><option value="cmms-intake">CMMS Intake</option><option value="intake/email">Email Intake</option><option value="orchestration-preview">Orchestration Preview</option><option value="cmms-assistant">CMMS Assistant Chat</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select></div></div>
          <div><label>Environment</label><div class="select-wrap"><select id="tEnv" class="cmms-select" onchange="syncWorkflowModeFromEnvironment('tEnv', 'tWorkflowMode')">${envOptions()}</select></div></div></div>
          <div id="testWorkflowRow"><label>Workflow</label><div class="select-wrap"><select id="tWorkflowMode" class="cmms-select"><option value="fast" selected>Fast</option><option value="full">Full</option></select></div></div>
          <div id="testModeHelp" class="notice"></div>
          <div id="testInputPanel"></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Response</div><div class="playground-subtitle" id="inputSourceLabel">Input source: none</div></div><span id="runStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="tReadiness" class="readiness"><strong>Work order readiness</strong><div class="muted">Run CMMS Intake to evaluate whether enough validated information exists for a human-controlled workflow.</div></div>
            ${collapsiblePanel("Intake Metadata", `<div id="tMetadata"><span class="muted">Run CMMS Intake to extract metadata.</span></div>`)}
            ${collapsiblePanel("Code Normalization", `<div id="tCodeNormalization"><span class="muted">Run CMMS Intake to see code normalization suggestions.</span></div>`)}
            ${collapsiblePanel("Safety Review", `<div id="tReview"><span class="muted">Run CMMS Intake to see advisory safety review.</span></div>`)}
            ${collapsiblePanel("Workflow Trace", `<div id="tTrace"><span class="muted">Run CMMS Intake to see trace steps.</span></div>`)}
            <div class="result-grid">
              ${collapsiblePanel("Contract Validation", `<div id="tContract"><span class="muted">Run a request to see contract validation.</span></div>`)}
              ${collapsiblePanel("Environment Validation", `<div id="tValidation"><span class="muted">Run a request to see environment validation.</span></div>`)}
            </div>
            ${collapsiblePanel("Extracted JSON", `<div class="status-line collapsible-toolbar">${outputToolbar("tOut", { hide: true, clear: true })}</div><pre id="tOut" class="console-output">{}</pre>`, { open: true, dark: true })}
          </div>
        </div>
      </div>`, "", "Run advisory AI endpoints with the minimum controls visible first.");
      syncWorkflowModeFromEnvironment('tEnv', 'tWorkflowMode');
      renderTestInputPanel();
      updateTestModeUi();
      renderTestModeHelp();
    }
    function emailIntake() {
      pageShell("Email Intake", `<div class="grid">
        <div class="card playground span-4"><div class="playground-header"><div><div class="playground-title">Email</div><div class="playground-subtitle">Paste or import.</div></div><span class="pill">email_api</span></div><div class="card-body stack">
          <details class="credentials-panel"><summary>Test API credentials</summary><div class="compact-field-row"><div><label>API key</label><input id="eKey" type="password" value="${escapeAttr(state.defaultApiKey)}" placeholder="Paste generated API key" oninput="rememberApiKey(this.value)"></div><button class="secondary" onclick="forgetApiKey()">Forget key</button></div></details>
          <label>Environment</label><select id="eEnv">${envOptions()}</select>
          <div class="ai-panel stack email-compose">
            <label>From</label><input id="emailFrom" placeholder="tenant@example.com">
            <label>To</label><input id="emailTo" placeholder="maintenance@example.com">
            <label>Subject</label><input id="emailSubject" placeholder="Leak in ARC 205">
            <label>Body</label><textarea id="emailBody" class="compact-textarea" placeholder="Paste email body"></textarea>
            <input id="emailImportFile" type="file" accept=".eml,.txt,message/rfc822,text/plain" style="display:none" onchange="handleEmailImport(event)">
            <div class="compact-actions email-actions"><button class="secondary" onclick="$('emailImportFile').click()">Import</button><button class="secondary" onclick="clearEmailIntake()">Clear</button><button id="eRunBtn" onclick="runEmailIntake()">Run Email</button></div>
          </div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Response</div><div class="playground-subtitle" id="inputSourceLabel">Input source: email API</div></div><span id="runStatus" class="pill">Ready</span></div>
          <div class="run-surface">
            <div id="tReadiness" class="readiness"><strong>Work order readiness</strong><div class="muted">Run Email to evaluate the request.</div></div>
            ${collapsiblePanel("Intake Metadata", `<div id="tMetadata"><span class="muted">Run Email to extract metadata.</span></div>`)}
            ${collapsiblePanel("Code Normalization", `<div id="tCodeNormalization"><span class="muted">Run Email to see code normalization suggestions.</span></div>`)}
            ${collapsiblePanel("Safety Review", `<div id="tReview"><span class="muted">Run Email to see advisory safety review.</span></div>`)}
            ${collapsiblePanel("Workflow Trace", `<div id="tTrace"><span class="muted">No run yet.</span></div>`)}
            <div class="result-grid">
              ${collapsiblePanel("Contract Validation", `<div id="tContract"><span class="muted">No run yet.</span></div>`)}
              ${collapsiblePanel("Environment Validation", `<div id="tValidation"><span class="muted">No run yet.</span></div>`)}
            </div>
            ${collapsiblePanel("Extracted JSON", `<div class="status-line collapsible-toolbar">${outputToolbar("tOut", { hide: true, clear: true })}</div><pre id="tOut" class="console-output">{}</pre>`, { open: true, dark: true })}
          </div>
        </div>
      </div>`, "", "Turn pasted maintenance emails into controlled advisory intake drafts.");
    }
    function renderTestInputPanel() {
      if (!$("testInputPanel")) return;
      const supported = getSpeechRecognitionCtor();
      state.voiceSupported = Boolean(supported);
      $("testInputPanel").innerHTML = `<div class="ai-panel stack">
          <div id="testEmailFields" class="stack hidden">
            <div class="compact-field-row compact-field-row-two">
              <div><label>From</label><input id="testEmailFrom" value="operator@example.local" placeholder="requester@example.com"></div>
              <div><label>To</label><input id="testEmailTo" value="maintenance@example.local" placeholder="maintenance@example.com"></div>
            </div>
            <label>Subject</label><input id="testEmailSubject" value="Test Console Email Intake" placeholder="Email subject">
          </div>
          <label id="testContentLabel">Content</label>
          <div class="input-with-voice"><textarea id="tText" class="compact-textarea test-console-textarea">The air conditioner in ARC room 205 is making loud noise and the room is too warm. My name is Leon, phone is 1234, email address is bdsrca@gmail.com. I wanted it done by the end of this week.</textarea><button id="voiceStartBtn" class="voice-icon-button secondary" aria-label="Start voice input" title="Start voice input" onclick="startVoiceRecognition()" ${supported ? "" : "disabled"}>🎙</button></div>
          <div class="compact-actions test-console-actions"><button id="runTestBtn" onclick="runTest('text')">Run Text</button><button class="secondary" onclick="clearVoiceTranscript()">Clear</button><button class="secondary" onclick="openSaveCurrentTestCase()">Save as Test Case</button><button class="secondary" onclick="runMatchingTestCase()">Run Matching Test</button></div>
        </div>
        <details class="voice-settings" id="voiceSettings"><summary>Voice settings</summary><div class="voice-settings-body stack">
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
          <div class="button-grid"><button class="secondary" onclick="stopVoiceRecognition()" ${supported ? "" : "disabled"}>Stop listening</button></div>
          <div class="muted">Listening stops automatically after 5 seconds without detected speech.</div>
          <div id="voiceMessage" class="muted">Speech recognition is handled by the browser. This app does not store audio. Review the transcript before sending.</div>
        </div></details>`;
    }
    function updateTestModeUi() {
      const ep = $("tEndpoint")?.value || "cmms-intake";
      const isEmail = ep === "intake/email";
      const isOrchestration = ep === "orchestration-preview";
      if ($("testEmailFields")) $("testEmailFields").classList.toggle("hidden", !isEmail);
      if ($("testWorkflowRow")) $("testWorkflowRow").classList.toggle("hidden", isEmail || ep === "extract-work-order-fields" || ep === "summarize-work-order" || ep === "cmms-assistant");
      if ($("testContentLabel")) $("testContentLabel").textContent = isEmail ? "Email body" : isOrchestration ? "Work request" : "Content";
      if ($("runTestBtn")) $("runTestBtn").textContent = isEmail ? "Run Email Intake" : isOrchestration ? "Run Orchestration Preview" : "Run";
    }
    async function renderTestModeHelp() {
      if (!$("testModeHelp")) return;
      const ep = $("tEndpoint")?.value || "cmms-intake";
      const copy = {
        "cmms-intake": "Controlled extraction workflow: contract validation, environment validation, readiness, and advisory drafts.",
        "intake/email": "Email-shaped intake test. The text box is sent as the email body through the existing controlled email intake endpoint.",
        "orchestration-preview": "Runs CMMS Intake in full workflow mode so orchestration, assignment, inventory, action-plan, and gate details are visible.",
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
      if ($("voiceStartBtn")) $("voiceStartBtn").classList.toggle("listening", status === "Listening");
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
      if ($("emailFrom")) $("emailFrom").value = "";
      if ($("emailTo")) $("emailTo").value = "";
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
    function copyEmailToText() {
      if ($("tText")) $("tText").value = buildEmailIntakeContent();
    }
    function clearEmailIntake() {
      if ($("emailFrom")) $("emailFrom").value = "";
      if ($("emailTo")) $("emailTo").value = "";
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
        rememberApiKey($("eKey").value);
        const data = await api("/api/ai/intake/email", { method: "POST", headers: { "x-api-key": state.defaultApiKey }, body: JSON.stringify(payload) });
        if ($("inputSourceLabel")) $("inputSourceLabel").textContent = "Input source: email API";
        if ($("runStatus")) $("runStatus").textContent = "Complete";
        setConsoleOutput("tOut", data);
        state.lastTestResponse = data;
        state.metadataReviewExtracted = cloneConsoleData(data);
        state.lastTestInput = { endpoint: "intake/email", environment_code: $("eEnv").value, text: buildEmailIntakeContent(), source: "email_api" };
        renderContractValidation(data.contract);
        renderTestValidation(data.ai_validation);
        renderReadiness(data);
        renderIntakeMetadata(data);
        renderCodeNormalization(data.code_normalization);
        renderSafetyReview(data.review);
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
      let path = `/api/ai/${ep}`;
      let body = { text, environment_code: $("tEnv").value };
      if (ep === "intake/email") {
        path = "/api/ai/intake/email";
        body = {
          from_email: $("testEmailFrom").value,
          to_email: $("testEmailTo").value,
          subject: $("testEmailSubject").value,
          body: text,
          environment_code: $("tEnv").value
        };
          } else if (ep === "orchestration-preview") {
            path = "/api/ai/cmms-intake";
            body.workflow_mode = "full";
            body.source = "orchestration_preview";
          }
          if (ep === "cmms-intake") body.workflow_mode = $("tWorkflowMode").value;
          if (source !== "text" && ep !== "intake/email" && ep !== "orchestration-preview") body.source = source;
      try {
        setRunLoading(true);
        rememberApiKey($("tKey").value);
        const data = await api(path, { method: "POST", headers: { "x-api-key": state.defaultApiKey }, body: JSON.stringify(body) });
        const sourceLabels = { text: "text", voice_transcript: "voice transcript", email_paste: "email paste" };
        if ($("inputSourceLabel")) $("inputSourceLabel").textContent = `Input source: ${sourceLabels[source] || source}`;
        if ($("runStatus")) $("runStatus").textContent = "Complete";
        setConsoleOutput("tOut", data);
        state.lastTestResponse = data;
        state.metadataReviewExtracted = cloneConsoleData(data);
        state.lastTestInput = { endpoint: ep, environment_code: $("tEnv").value, text, source };
        renderContractValidation(data.contract);
        renderTestValidation(data.ai_validation);
        renderReadiness(data);
        renderIntakeMetadata(data);
        renderCodeNormalization(data.code_normalization);
        renderSafetyReview(data.review);
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

    function renderIntakeMetadata(data) {
      if (!$("tMetadata")) return;
      const submission = data?.submission || data?.result?.submission || {};
      const request = data?.request || data?.result?.request || {};
      const location = request.location || {};
      $("tMetadata").innerHTML = `<div class="metadata-grid">
          <div class="metadata-item"><label>Submitted by</label><input id="metadataSubmittedBy" value="${escapeAttr(submission.submitted_by || "")}"></div>
          <div class="metadata-item"><label>Email</label><input id="metadataEmail" type="email" value="${escapeAttr(submission.submitted_email || "")}"></div>
          <div class="metadata-item"><label>Phone</label><input id="metadataPhone" value="${escapeAttr(submission.submitted_phone || "")}"></div>
          <div class="metadata-item"><label>Requested due</label><input type="date" id="metadataDue" value="${escapeAttr(request.requested_due || "")}"></div>
          <div class="metadata-item"><label>Building</label><input id="metadataBuilding" value="${escapeAttr(location.building || "")}"></div>
          <div class="metadata-item"><label>Room</label><input id="metadataRoom" value="${escapeAttr(location.room || "")}"></div>
          <div class="metadata-item"><label>Method</label><div class="metadata-value">${submission.submitted_method ? escapeHtml(submission.submitted_method) : '<span class="muted">-</span>'}</div></div>
          <div class="metadata-item"><label>Source phrase</label><div class="metadata-value">${request.requested_due_raw ? escapeHtml(request.requested_due_raw) : '<span class="muted">-</span>'}</div></div>
        </div>
        <div class="row" style="margin-top:10px"><button onclick="applyMetadataReview()">Apply</button><button class="secondary" onclick="resetMetadataReview()">Reset</button></div>`;
    }

    function metadataReviewValue(id) {
      return ($(id)?.value || "").trim() || null;
    }

    async function applyMetadataReview() {
      const data = state.lastTestResponse;
      if (!data?.run_id) return;
      const patch = {
        submitted_by: metadataReviewValue("metadataSubmittedBy"),
        submitted_email: metadataReviewValue("metadataEmail"),
        submitted_phone: metadataReviewValue("metadataPhone"),
        requested_due: metadataReviewValue("metadataDue"),
        building: metadataReviewValue("metadataBuilding"),
        room: metadataReviewValue("metadataRoom")
      };
      let review = null;
      try {
        review = await api(`/api/admin/workflow-runs/${data.run_id}/metadata-review/apply`, { method: "POST", body: JSON.stringify(patch) });
      } catch (e) {
        setConsoleOutput("tOut", e.data || { error: e.message });
        return;
      }
      data.submission = review.submission;
      data.request = review.request;
      data.metadata_review = review.metadata_review;
      if (data.result) {
        data.result.submission = review.submission;
        data.result.request = review.request;
        data.result.building = review.request?.location?.building || null;
        data.result.room = review.request?.location?.room || null;
        data.result.metadata_review = review.metadata_review;
      }
      state.lastTestResponse = data;
      setConsoleOutput("tOut", data);
      renderIntakeMetadata(data);
    }

    function resetMetadataReview() {
      if (!state.metadataReviewExtracted) return;
      const data = cloneConsoleData(state.metadataReviewExtracted);
      state.lastTestResponse = data;
      setConsoleOutput("tOut", data);
      renderIntakeMetadata(data);
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

    function renderCodeNormalization(block) {
      if (!$("tCodeNormalization")) return;
      if (!block) {
        $("tCodeNormalization").innerHTML = '<span class="muted">No code normalization returned for this endpoint.</span>';
        return;
      }
      const status = block.status || "unknown";
      const cls = status === "applied" || status === "no_suggestions" ? "ok" : status === "skipped" || status === "rejected" ? "warning" : "danger";
      const suggestions = block.suggestions || [];
      const rejected = block.rejected || [];
      const applied = block.applied || {};
      $("tCodeNormalization").innerHTML = `<div class="status-line"><span class="pill ${cls}">${escapeHtml(status)}</span><span class="muted">${block.enabled ? "suggestion agent enabled" : "not run"}</span></div>
        ${block.message ? `<p class="muted">${escapeHtml(block.message)}</p>` : ""}
        <h3>Applied</h3><pre style="min-height:80px">${JSON.stringify(applied, null, 2)}</pre>
        <h3>Accepted suggestions</h3>${suggestions.length ? `<table><thead><tr><th>Field</th><th>Input</th><th>Code</th><th>Confidence</th><th>Reason</th></tr></thead><tbody>${suggestions.map(s => `<tr><td>${escapeHtml(s.field || "")}</td><td>${escapeHtml(s.input_value || "")}</td><td>${escapeHtml(s.suggested_code || "")}</td><td>${escapeHtml(s.confidence ?? "")}</td><td>${escapeHtml(s.reason || "")}</td></tr>`).join("")}</tbody></table>` : '<p class="muted">None</p>'}
        <h3>Rejected suggestions</h3>${rejected.length ? `<table><thead><tr><th>Field</th><th>Code</th><th>Reason</th></tr></thead><tbody>${rejected.map(s => `<tr><td>${escapeHtml(s.field || "")}</td><td>${escapeHtml(s.suggested_code || "")}</td><td>${escapeHtml(s.reason_code || "unknown")}</td></tr>`).join("")}</tbody></table>` : '<p class="muted">None</p>'}`;
    }

    function renderSafetyReview(review) {
      if (!$("tReview")) return;
      if (!review) {
        $("tReview").innerHTML = '<span class="muted">No safety review returned for this endpoint.</span>';
        return;
      }
      const status = review.status || "unknown";
      const cls = status === "pass" ? "ok" : status === "warning" || status === "skipped" ? "warning" : "danger";
      $("tReview").innerHTML = `<div class="status-line"><span class="pill ${cls}">${escapeHtml(status)}</span><span class="muted">Source: ${escapeHtml(review.source || "safety_reviewer_agent")}</span></div>
        <div style="margin-top:8px">Human review recommended: <strong>${review.human_review_recommended ? "Yes" : "No"}</strong></div>
        <h3>Risk flags</h3>${issueList(review.risk_flags)}
        <h3>Notes</h3>${issueList(review.notes)}
        ${review.message ? `<p class="muted">${escapeHtml(review.message)}</p>` : ""}`;
    }

    async function renderWorkflowTraceFromResponse(data, targetId) {
      if (!$(targetId)) return;
      if (!data?.trace?.available || !data.trace.run_id) {
        $(targetId).innerHTML = '<span class="muted">No workflow trace for this response.</span>';
        return;
      }
      try {
        const trace = await api(`/api/admin/workflow-runs/${data.trace.run_id}`);
        state.lastWorkflowTrace = trace;
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
      return renderWorkflowRunDetail(trace);
    }

    function renderWorkflowRunDetail(trace) {
      const cmmsPushStep = getTraceStep(trace, "cmms_auto_push");
      const cmmsPush = cmmsPushStep?.output_json || {};
      return `<div class="stack">
        <div class="status-line"><div><strong>Workflow Run Detail</strong><div class="muted">${escapeHtml(trace.run_id)} · ${escapeHtml(trace.endpoint || "")} · ${escapeHtml(trace.environment_code || "")} · ${trace.duration_ms ?? ""} ms</div></div><span class="pill ${trace.status === "failed" ? "danger" : trace.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(trace.status)}</span></div>
        <div class="metadata-grid">
          <div class="metadata-item"><label>Source</label><div class="metadata-value">${escapeHtml(trace.source || "")}</div></div>
          <div class="metadata-item"><label>Started</label><div class="metadata-value">${escapeHtml(trace.started_at || "")}</div></div>
          <div class="metadata-item"><label>Finished</label><div class="metadata-value">${escapeHtml(trace.finished_at || "")}</div></div>
          <div class="metadata-item"><label>CMMS Push</label><div class="metadata-value">${statusPill(cmmsPush.status || "not_run")}</div></div>
        </div>
        <div class="row"><button class="secondary" onclick="openCreateTestCaseFromRunModal('${escapeAttr(trace.run_id)}')">Create Test Case</button><button class="secondary" onclick="replayWorkflowRun('${escapeAttr(trace.run_id)}')">Replay Run</button><button class="secondary" onclick="navigator.clipboard?.writeText(JSON.stringify(state.lastWorkflowTrace || {}, null, 2))">Copy Run JSON</button></div>
        ${renderTraceMetadataReview(trace.metadata_review)}
        ${renderWorkflowTimeline(trace)}
        <div class="result-grid">
          ${renderTraceStepPanel(trace, "output_contract_validation", "Contract Validation")}
          ${renderTraceStepPanel(trace, "code_normalization_suggestion_agent", "Code Normalization")}
          ${renderTraceStepPanel(trace, "environment_validation", "Environment Validation")}
          ${renderTraceStepPanel(trace, "safety_review", "Safety Review")}
          ${renderTraceStepPanel(trace, "orchestration_summary", "Orchestration Summary")}
          ${renderTraceStepPanel(trace, "cmms_auto_push", "CMMS Push Gate")}
        </div>
      </div>`;
    }

    function getTraceStep(trace, stepName) {
      return (trace.steps || []).find(step => step.step_name === stepName);
    }

    function renderWorkflowTimeline(trace) {
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
      return `<div class="ai-panel"><div class="status-line"><h3>Step Timeline</h3><span class="pill">${(trace.steps || []).length} steps</span></div>${rows || '<p class="muted">No steps recorded.</p>'}</div>`;
    }

    function renderTraceStepPanel(trace, stepName, label) {
      const step = getTraceStep(trace, stepName);
      if (!step) return `<div class="ai-panel"><div class="status-line"><h3>${escapeHtml(label)}</h3><span class="pill warning">not_run</span></div><p class="muted">No ${escapeHtml(label)} step was recorded for this run.</p></div>`;
      const output = step.output_json || {};
      const summary = step.output_summary || step.error_message || "";
      return `<div class="ai-panel"><div class="status-line"><h3>${escapeHtml(label)}</h3><span class="pill ${step.status === "failed" ? "danger" : step.status === "warning" ? "warning" : step.status === "passed" ? "ok" : ""}">${escapeHtml(step.status)}</span></div>
        ${summary ? `<p class="muted">${escapeHtml(summary)}</p>` : ""}
        <pre style="min-height:150px">${escapeHtml(JSON.stringify(output, null, 2))}</pre>
      </div>`;
    }

    function renderTraceMetadataReview(review) {
      if (!review) return "";
      const extracted = review.extracted || {};
      const currentLocation = review.request?.location || {};
      const extractedLocation = extracted.request?.location || {};
      const rows = [
        ["Submitted by", extracted.submission?.submitted_by, review.submission?.submitted_by],
        ["Email", extracted.submission?.submitted_email, review.submission?.submitted_email],
        ["Phone", extracted.submission?.submitted_phone, review.submission?.submitted_phone],
        ["Requested due", extracted.request?.requested_due, review.request?.requested_due],
        ["Location", [extractedLocation.building, extractedLocation.room].filter(Boolean).join(" "), [currentLocation.building, currentLocation.room].filter(Boolean).join(" ")]
      ].map(([label, extractedValue, reviewedValue]) => `<div class="status-line" style="border-bottom:1px solid #eef0f3;padding:6px 0"><strong>${escapeHtml(label)}</strong><span class="muted">${escapeHtml(extractedValue || "-")} -> ${escapeHtml(reviewedValue || "-")}</span></div>`).join("");
      const corrected = review.metadata_review?.corrected_fields || [];
      const handoffTarget = handoffCandidateTarget(review.run_id);
      const handoff = review.metadata_review?.reviewed ? `<div class="row" style="margin-top:10px"><button class="secondary" onclick="loadCmmsHandoffCandidate('${escapeAttr(review.run_id)}')">CMMS Candidate</button></div><pre id="${escapeAttr(handoffTarget)}" style="display:none;min-height:120px;margin-top:8px"></pre>` : "";
      return `<div class="ai-panel" style="margin:10px 0"><div class="status-line"><h3>Intake Metadata Review</h3><span class="pill ${review.metadata_review?.reviewed ? "ok" : "warning"}">${review.metadata_review?.reviewed ? "Reviewed" : "Extracted"}</span></div>${rows}<div class="muted" style="margin-top:8px">Corrected: ${escapeHtml(corrected.length ? corrected.join(", ") : "none")}</div>${handoff}</div>`;
    }

    function handoffCandidateTarget(runId) {
      return `handoffCandidate_${String(runId || "").replace(/[^A-Za-z0-9_-]/g, "_")}`;
    }

    async function loadCmmsHandoffCandidate(runId) {
      const target = $(handoffCandidateTarget(runId));
      if (!target) return;
      try {
        const candidate = await api(`/api/admin/workflow-runs/${runId}/cmms-handoff-candidate`);
        target.style.display = "block";
        target.textContent = JSON.stringify(candidate, null, 2);
      } catch (e) {
        target.style.display = "block";
        target.textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
      }
    }

    function issueList(items) {
      if (!items || !items.length) return '<p class="muted">None</p>';
      return `<ul>${items.map(i=>`<li><strong>${escapeHtml(i.field)}</strong>: ${escapeHtml(i.message)} <span class="muted">(${escapeHtml(i.value ?? "")})</span></li>`).join("")}</ul>`;
    }

    function outputToolbar(id, options = {}) {
      const hide = options.hide ? `<button class="secondary" onclick="collapseOutputPanel('${id}')">Hide</button>` : "";
      const clear = options.clear ? `<button class="secondary" onclick="clearConsoleOutput('${id}')">Clear</button>` : "";
      return `<span class="row" style="gap:6px"><label style="margin:0;color:inherit"><input id="${id}Pretty" type="checkbox" checked onchange="refreshConsoleOutput('${id}')"> Pretty</label><button class="secondary" onclick="copyConsoleOutput('${id}')">Copy</button><button class="secondary" onclick="downloadConsoleOutput('${id}')">Download</button>${hide}${clear}</span>`;
    }

    function setConsoleOutput(id, value, isJson = true) {
      state.outputs[id] = { value, isJson };
      refreshConsoleOutput(id);
    }

    function cloneConsoleData(value) {
      return JSON.parse(JSON.stringify(value));
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

    function collapseOutputPanel(id) {
      const panel = $(id)?.closest("details");
      if (panel) panel.open = false;
    }

    function clearConsoleOutput(id) {
      setConsoleOutput(id, {});
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
        review_status: response.review?.status ?? null,
        review_human_review_recommended: response.review?.human_review_recommended ?? null,
        review_risk_flags_contains: response.review?.risk_flags?.length ? response.review.risk_flags : [],
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
        renderSafetyReview(data.actual_json.review);
        renderWorkflowTraceFromResponse(data.actual_json, "tTrace");
      }
    }

    function buildExpectedJsonFromRunTrace(trace) {
      const contract = getTraceStep(trace, "output_contract_validation")?.output_json || {};
      const result = contract.normalized_payload || {};
      const validation = getTraceStep(trace, "environment_validation")?.output_json || {};
      const issueFields = rows => (rows || []).map(item => item?.field).filter(Boolean);
      const summary = String(result.summary || "").trim();
      return {
        summary_contains: summary ? [summary.slice(0, 40).trim()] : [],
        building: result.building ?? null,
        room: result.room ?? null,
        priority: result.priority ?? null,
        work_order_type: result.work_order_type ?? null,
        assign_to: result.assign_to ?? null,
        issue_to: result.issue_to ?? null,
        job_type: result.job_type ?? null,
        contract_valid: contract.valid ?? null,
        environment_valid: validation.valid ?? null,
        expected_errors: issueFields(validation.errors),
        expected_warnings: issueFields(validation.warnings)
      };
    }

    function openCreateTestCaseFromRunModal(runId) {
      const trace = state.lastWorkflowTrace?.run_id === runId ? state.lastWorkflowTrace : { run_id: runId };
      const expected = buildExpectedJsonFromRunTrace(trace);
      document.body.insertAdjacentHTML("beforeend", `<div class="modal-backdrop" id="runTestCaseModal"><div class="modal" style="max-width:860px"><h2>Create Test Case From Run</h2><div class="modal-body stack">
        <div class="notice">Creates a regression case from stored workflow input when available. Edit the expected JSON before saving.</div>
        <label>Name</label><input id="runTcName" value="${escapeAttr(`Replay ${runId}`)}">
        <div class="compact-field-row compact-field-row-two"><div><label>Endpoint</label><input id="runTcEndpoint" value="${escapeAttr(trace.endpoint || "")}" disabled></div><div><label>Environment</label><input id="runTcEnv" value="${escapeAttr(trace.environment_code || "")}" disabled></div></div>
        <label>Expected JSON</label><textarea id="runTcExpected" style="min-height:260px">${escapeHtml(JSON.stringify(expected, null, 2))}</textarea>
        <label>Tags</label><input id="runTcTags" value="trace">
        <label>Notes</label><textarea id="runTcNotes">Created from workflow run ${escapeHtml(runId)}</textarea>
      </div><div class="modal-actions"><button class="secondary" onclick="$('runTestCaseModal').remove()">Cancel</button><button onclick="saveTestCaseFromRunModal('${escapeAttr(runId)}')">Save Test Case</button></div></div></div>`);
    }

    async function saveTestCaseFromRunModal(runId) {
      let expected;
      try { expected = JSON.parse($("runTcExpected").value); } catch { alert("Expected JSON is invalid."); return; }
      try {
        const data = await api(`/api/admin/workflow-runs/${runId}/create-test-case`, { method: "POST", body: JSON.stringify({ name: $("runTcName").value, expected_json: expected, tags: $("runTcTags").value, notes: $("runTcNotes").value }) });
        $("runTestCaseModal")?.remove();
        alert(`Created test case #${data.test_case_id}`);
      } catch (e) {
        alert(e.message);
      }
    }

    async function createTestCaseFromTrace(runId) { openCreateTestCaseFromRunModal(runId); }

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
          <div class="command-bar quiet-toolbar"><button onclick="newTestCase()">New</button><button class="secondary" onclick="runBatchTestCases()">Run Enabled Batch</button><button class="secondary" onclick="testCases()">Refresh</button></div>
          <div id="testCaseTable">${tableScroll(renderTestCasesTable(cases))}</div>
        </div></div>
        <div class="card span-4"><h2>Test Case Detail</h2><div class="card-body stack detail-form" id="testCaseDetail"><p class="muted">Select a test case or create a new one.</p></div></div>
        <div class="card span-12"><h2>Recent Test Case Runs</h2><div class="card-body" id="testCaseRuns">${tableScroll(renderTestCaseRunsTable(runs))}</div></div>
      </div>`, "", "Review saved cases and recent runs without showing every test control at once.");
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
          <div class="command-bar"><button onclick="newTestSuite()">New Suite</button><button class="secondary" onclick="ensureSafetyReviewerSmokeSuite()">Safety Reviewer Smoke Suite</button><button class="secondary" onclick="runAllSuites()">Run Enabled Suites</button><button class="secondary" onclick="testSuites()">Refresh</button></div>
          <div id="testSuiteTable">${renderTestSuitesTable(suites)}</div>
        </div></div>
        <div class="card span-4"><h2>Suite Detail</h2><div class="card-body stack detail-form" id="testSuiteDetail"><p class="muted">Select a suite or create a new one.</p></div></div>
        <div class="card span-12"><h2>Suite Runs</h2><div class="card-body" id="testSuiteRuns">${renderTestSuiteRunsTable(runs)}</div></div>
      </div>`, "", "Review output contracts and test schema changes before promotion.");
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

    async function ensureSafetyReviewerSmokeSuite() {
      const env = window.prompt("Environment code", "DEFAULT");
      if (env === null) return;
      const suite = await api("/api/admin/test-suites/safety-reviewer-smoke/ensure", { method: "POST", body: JSON.stringify({ environment_code: env || "DEFAULT", required_for_promotion: false }) });
      await testSuites();
      await showTestSuiteDetail(suite.suite_id);
    }

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
          <details class="credentials-panel"><summary>Test API credentials</summary><div class="compact-field-row"><div><label>API key</label><input id="bKey" type="password" value="${escapeAttr(state.defaultApiKey)}" placeholder="Paste generated API key" oninput="rememberApiKey(this.value); buildCall()"></div><button class="secondary" onclick="forgetApiKey()">Forget key</button></div></details>
          <div class="compact-field-row compact-field-row-two"><div><label>Endpoint</label><select id="bEndpoint" onchange="buildCall()"><option value="cmms-intake">CMMS Intake</option><option value="intake/email">Email Intake</option><option value="cmms-assistant">CMMS Assistant</option><option value="extract-work-order-fields">Extract Fields</option><option value="summarize-work-order">Summarize</option></select></div>
          <div><label>Environment</label><select id="bEnv" onchange="buildCall()">${envOptions()}</select></div></div>
          <div class="compact-field-row compact-field-row-two"><div><label>Input source</label><select id="bSource" onchange="buildCall()"><option value="text">text</option><option value="voice_transcript">voice_transcript</option><option value="email_paste">email_paste</option><option value="email_mailbox">email_mailbox_reserved</option></select></div>
          <div><label>Example language</label><select id="bLanguage" onchange="buildCall()"><option value="curl">curl</option><option value="powershell">PowerShell</option><option value="javascript">JavaScript fetch</option><option value="python">Python requests</option></select></div></div>
          <label>Text</label><textarea id="bText" class="compact-textarea" oninput="buildCall()">The air conditioner in ARC room 205 is making loud noise.</textarea>
          <label><input id="bReturnValidation" type="checkbox" checked style="width:auto" onchange="buildCall()"> Include readiness validation in examples</label>
          <div class="compact-actions"><button onclick="buildCall()">Generate</button><button class="secondary" onclick="runBuilderValidation()">Run + Validate</button></div>
          <div class="ai-panel stack"><strong>API Documentation</strong><p class="muted">Export a public-safe Markdown package for endpoint usage, authentication, environment codes, and CMMS safety boundaries.</p><div class="compact-actions"><button class="secondary" onclick="copyApiDocsMarkdown()">Copy API Docs</button><button class="secondary" onclick="downloadApiDocsMarkdown()">Download API Docs</button></div></div>
        </div></div>
        <div class="card playground span-8"><div class="playground-header"><div><div class="playground-title">Generated calls</div><div class="playground-subtitle">Selectable client examples, request body, response contract, and readiness logic.</div></div><span class="pill">Builder</span></div><div class="run-surface">
          ${collapsiblePanel("Endpoint notes", `<div id="bDoc"></div>`)}
          <div id="bValidationOut" class="readiness warn"><strong>Validation preview</strong><div class="muted">Use Run + Validate to call the endpoint and check whether the response has enough validated information.</div></div>
          ${collapsiblePanel("Generated examples", `<div class="status-line collapsible-toolbar">${outputToolbar("bOut")}</div><pre id="bOut" class="code-output"></pre>`, { open: true, dark: true })}
        </div></div>
      </div>`, "", "Compose controlled API calls without exposing every secondary option up front.");
      buildCall();
    }
    function buildCall() {
      const ep = $("bEndpoint").value;
      const bodyObj = builderRequestBody(ep);
      const body = JSON.stringify(bodyObj, null, 2);
      const uri = `${$("bBase").value}/api/ai/${ep}`;
      const includeValidation = $("bReturnValidation").checked && (ep === "cmms-intake" || ep === "intake/email");
      const apiKey = $("bKey").value;
      const examples = builderLanguageExamples(uri, body, apiKey, includeValidation);
      const language = $("bLanguage").value;
      const generated = examples[language] || examples.curl;
      const languageLabels = { curl: "curl", powershell: "PowerShell", javascript: "JavaScript fetch", python: "Python requests" };
      const label = languageLabels[language] || "curl";
      const responseNotes = endpointDoc(ep, includeValidation);
      $("bDoc").innerHTML = responseNotes;
      setConsoleOutput("bOut", `Generated example: ${label}\n${generated}\n\nJSON body:\n${body}\n\nExpected response fields:\n${expectedFields(ep).join("\\n")}`, false);
    }

    function builderLanguageExamples(uri, body, apiKey, includeValidation) {
      const psValidation = includeValidation ? `\n\n# Readiness check: advisory only, does not create a work order\n$ContractOk = $Response.contract.valid\n$EnvironmentOk = $Response.ai_validation.valid\n$CanCreateWorkOrder = $Response.validation.can_create_work_order\n$MissingFields = $Response.validation.missing_fields -join ", "\n[pscustomobject]@{\n  ContractValidation = $ContractOk\n  EnvironmentValidation = $EnvironmentOk\n  EnoughInformation = $CanCreateWorkOrder\n  MissingFields = $MissingFields\n  AdvisoryOnly = $true\n}` : "";
      const ps = `$Headers = @{ "x-api-key" = "${apiKey}" }\n$Body = @'\n${body}\n'@\n$Response = Invoke-RestMethod -Method POST -Uri "${uri}" -Headers $Headers -ContentType "application/json" -Body $Body\n$Response | ConvertTo-Json -Depth 20${psValidation}`;
      const curl = `curl -X POST "${uri}" \\\n  -H "x-api-key: ${apiKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '${body.replaceAll("'", "\\'")}'`;
      const jsValidation = includeValidation ? `\nconst ready = Boolean(data.contract?.valid && data.ai_validation?.valid && data.validation?.can_create_work_order);\nconsole.log({ ready, missing_fields: data.validation?.missing_fields ?? [], advisory_only: true });` : "";
      const javascript = `const response = await fetch("${uri}", {\n  method: "POST",\n  headers: {\n    "x-api-key": "${apiKey}",\n    "Content-Type": "application/json"\n  },\n  body: JSON.stringify(${body})\n});\n\nif (!response.ok) throw new Error(await response.text());\nconst data = await response.json();\nconsole.log(data);${jsValidation}`;
      const pyValidation = includeValidation ? `\nready = bool(data.get("contract", {}).get("valid") and data.get("ai_validation", {}).get("valid") and data.get("validation", {}).get("can_create_work_order"))\nprint({\n    "ready": ready,\n    "missing_fields": data.get("validation", {}).get("missing_fields", []),\n    "advisory_only": True,\n})` : "";
      const python = `import json\nimport requests\n\npayload = json.loads(${JSON.stringify(body)})\nresponse = requests.post(\n    "${uri}",\n    headers={\n        "x-api-key": "${apiKey}",\n        "Content-Type": "application/json",\n    },\n    json=payload,\n    timeout=30,\n)\nresponse.raise_for_status()\ndata = response.json()\nprint(json.dumps(data, indent=2))${pyValidation}`;
      return { curl, powershell: ps, javascript, python };
    }

    function builderRequestBody(endpoint) {
      if (endpoint === "intake/email") {
        return {
          from_email: "tenant@example.com",
          to_email: "maintenance@example.com",
          subject: "Leak in ARC 205",
          body: $("bText").value,
          environment_code: $("bEnv").value
        };
      }
      const bodyObj = { text: $("bText").value, environment_code: $("bEnv").value };
      if ($("bSource").value !== "text") bodyObj.source = $("bSource").value;
      return bodyObj;
    }

    function endpointDoc(endpoint, includeValidation) {
      const docs = {
        "cmms-intake": ["POST /api/ai/cmms-intake", "Returns endpoint, environment_code, contract validation, result, ai_validation, advisory validation, drafts, and model.", "Use contract.valid plus ai_validation.valid plus validation.can_create_work_order to decide if the request has enough information for a human-controlled CMMS workflow."],
        "intake/email": ["POST /api/ai/intake/email", "Accepts email fields and extracts intake metadata from the email content.", "Runs the same advisory intake workflow with source email_api."],
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
        rememberApiKey($("bKey").value);
        const data = await api(`/api/ai/${ep}`, { method: "POST", headers: { "x-api-key": state.defaultApiKey }, body: JSON.stringify(body) });
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

    function apiDocsMarkdown() {
      return `# CMMS Local AI API Quick Docs

## Authentication

AI endpoints require \`x-api-key\`. Generated API keys call controlled AI endpoints only and do not grant admin portal access.

## Safety Boundary

- No generic \`/chat\` endpoint.
- Do not expose Ollama directly.
- AI output is contract-validated and environment-validated before use.
- CMMS push is controlled by deterministic gates, safety review, handoff readiness, and explicit connector configuration.
- Email sending is not automatic.

## Common Variables

\`\`\`text
API_BASE_URL=${$("bBase")?.value || location.origin}
ENVIRONMENT_CODE=${$("bEnv")?.value || "DEFAULT"}
LLM_API_KEY=replace-with-generated-key
\`\`\`

## Controlled AI Endpoints

### POST /api/ai/cmms-intake

Runs text intake, output contract validation, code normalization, environment validation, safety review, orchestration, and CMMS push gate preview.

### POST /api/ai/intake/email

Accepts \`from_email\`, \`to_email\`, \`subject\`, \`body\`, and \`environment_code\`. Uses the same controlled intake workflow with email source metadata.

### POST /api/ai/cmms-assistant

Controlled advisory assistant. It is not a generic chat endpoint and cannot write to CMMS.

### POST /api/ai/extract-work-order-fields

Extracts structured CMMS fields for debugging.

### POST /api/ai/summarize-work-order

Returns a concise summary only.

## Readiness Check

For intake responses, use:

\`\`\`text
contract.valid == true
ai_validation.valid == true
validation.can_create_work_order == true
review.status == "pass"
cmms_push.status in ["dry_run", "sent"]
\`\`\`

Passing readiness means the request is eligible for a controlled workflow. It does not mean an LLM directly created or approved a work order.
`;
    }

    async function copyApiDocsMarkdown() {
      await navigator.clipboard?.writeText(apiDocsMarkdown());
    }

    function downloadApiDocsMarkdown() {
      const blob = new Blob([apiDocsMarkdown()], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cmms-local-ai-api-docs-${new Date().toISOString().slice(0, 10)}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }
    async function environments() {
      await refreshBase();
      if (!state.envs.some(e => e.environment_code === state.selectedEnv)) state.selectedEnv = state.envs[0]?.environment_code || "DEFAULT";
      await loadEnvironmentCodes();
      await loadValidationRules();
      await loadCmmsConnector();
      await loadCmmsPushEvents();
      const env = state.envs.find(e => e.environment_code === state.selectedEnv) || {};
      pageShell("Environments", `<div class="resource-header">
        <div class="resource-title">Environment: ${env.environment_code || state.selectedEnv}</div>
        <div class="muted">Status: ${env.enabled ? "Enabled" : "Disabled"} &nbsp; Model: qwen3:8b &nbsp; Base URL: local &nbsp; Updated: ${env.updated_at || ""}</div>
      </div>
      <div class="command-bar">
        <span class="muted">Environment</span><select id="envPick" onchange="state.selectedEnv=this.value; environments()">${state.envs.map(e=>`<option value="${e.environment_code}" ${e.environment_code===state.selectedEnv?"selected":""}>${e.environment_code} - ${e.name}</option>`).join("")}</select>
        <span class="muted">Default workflow</span><select id="envDefaultWorkflowMode" onchange="patchEnvWorkflowMode(this.value)"><option value="fast" ${workflowModeForEnvironment(env) === "fast" ? "selected" : ""}>Fast</option><option value="full" ${workflowModeForEnvironment(env) === "full" ? "selected" : ""}>Full</option></select>
        <button class="secondary" onclick="showCreateEnv()">Create environment</button>
        <button class="secondary" onclick="seedDemoEnvironment()">Load demo setup</button>
        <button class="secondary" onclick="environments()">Refresh</button>
      </div>
      <div class="tabs">
        <button class="${state.envTab==='codes'?'active':''}" onclick="state.envTab='codes'; renderEnvironmentTab()">Code Lists</button>
        <button class="${state.envTab==='validation'?'active':''}" onclick="state.envTab='validation'; renderEnvironmentTab()">Validation Rules</button>
        <button class="${state.envTab==='connector'?'active':''}" onclick="state.envTab='connector'; renderEnvironmentTab()">CMMS Connector</button>
      </div>
      <details class="coming-soon-tabs"><summary>Coming soon</summary><div class="tabs"><button disabled>Overview</button><button disabled>Test Console</button><button disabled>API Examples</button><button disabled>Usage Logs</button><button disabled>Settings</button></div></details>
      <div id="envTab">${renderEnvironmentTabContent()}</div>`, "", "Manage environment-specific codes, validation rules, and CMMS connector settings.");
    }
    async function createEnv() {
      await api("/api/admin/environments", { method: "POST", body: JSON.stringify({ environment_code: $("envCode").value, name: $("envName").value, enabled: true }) });
      await refreshBase(); environments();
    }

    async function patchEnvWorkflowMode(value) {
      await api(`/api/admin/environments/${state.selectedEnv}`, { method: "PATCH", body: JSON.stringify({ default_workflow_mode: value }) });
      await refreshBase();
      environments();
    }

    function showCreateEnv() {
      const code = prompt("Environment code", "TEST");
      if (!code) return;
      const name = prompt("Environment name", "Test Environment") || code;
      api("/api/admin/environments", { method: "POST", body: JSON.stringify({ environment_code: code, name, enabled: true }) }).then(async () => { await refreshBase(); state.selectedEnv = code.toUpperCase(); environments(); });
    }

    async function seedDemoEnvironment() {
      const result = await api(`/api/admin/environments/${state.selectedEnv}/demo-setup`, { method: "POST" });
      await refreshBase();
      await loadEnvironmentCodes();
      await loadValidationRules();
      await loadCmmsConnector();
      await loadCmmsPushEvents();
      renderEnvironmentTab();
      alert(`Demo setup loaded for ${result.environment_code}: ${result.counts.assets || 0} assets, ${result.counts.technician_roster || 0} technicians, dry-run connector ready.`);
    }

    async function loadEnvironmentCodes() {
      state.codeData = await api(`/api/admin/environments/${state.selectedEnv}/codes`).catch(() => ({ rows: [] }));
    }

    async function loadValidationRules() {
      state.validationRules = await api(`/api/environments/${state.selectedEnv}/validation-rules`).catch(() => []);
    }

    async function loadCmmsConnector() {
      state.cmmsConnector = await api(`/api/admin/environments/${state.selectedEnv}/cmms-connector`).catch(() => ({ configured: false, secret_configured: false }));
    }

    async function loadCmmsPushEvents() {
      state.cmmsPushEvents = await api(`/api/admin/environments/${state.selectedEnv}/cmms-connector/push-events`).catch(() => []);
    }

    function renderEnvironmentTab() {
      $("envTab").innerHTML = renderEnvironmentTabContent();
    }

    function renderEnvironmentTabContent() {
      if (state.envTab === "validation") return renderValidationRulesTab();
      if (state.envTab === "connector") return renderCmmsConnectorTab();
      return renderCodeListsTab();
    }

    function renderCmmsConnectorTab() {
      const c = state.cmmsConnector || {};
      return `<div class="card"><h2>CMMS Connector</h2><div class="card-body">
        <div class="metadata-grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));align-items:start">
          <div><label>Endpoint URL</label><input id="cmmsEndpoint" value="${escapeAttr(c.endpoint_url || "")}" placeholder="https://cmms.example/api/work-orders"></div>
          <div><label>Auth Type</label><select id="cmmsAuthType"><option value="bearer" ${c.auth_type !== "header" ? "selected" : ""}>Bearer Token</option><option value="header" ${c.auth_type === "header" ? "selected" : ""}>Custom Header</option></select></div>
          <div><label>Header Name</label><input id="cmmsHeaderName" value="${escapeAttr(c.auth_header_name || "X-API-Key")}"></div>
          <div><label>Secret</label><input id="cmmsSecret" type="password" placeholder="${c.secret_configured ? "Configured - leave blank to keep" : "Required"}"></div>
          <div><label>Timeout Seconds</label><input id="cmmsTimeout" type="number" min="1" max="30" value="${escapeAttr(c.timeout_seconds || 5)}"></div>
          <div><label>HTTP Method</label><select id="cmmsMethod"><option value="POST" ${(c.http_method || "POST") === "POST" ? "selected" : ""}>POST</option><option value="PUT" ${c.http_method === "PUT" ? "selected" : ""}>PUT</option><option value="PATCH" ${c.http_method === "PATCH" ? "selected" : ""}>PATCH</option></select></div>
          <div><label>Success Status Codes</label><input id="cmmsSuccessCodes" value="${escapeAttr(c.success_status_codes || "200,201,202")}"></div>
          <div><label>External ID Path</label><input id="cmmsExternalPath" value="${escapeAttr(c.external_id_path || "")}" placeholder="id or data.workOrder.id"></div>
          <div><label>Payload Root Key</label><input id="cmmsPayloadRoot" value="${escapeAttr(c.payload_root_key || "")}" placeholder="workOrder"></div>
          <div><label>Static Headers JSON</label><textarea id="cmmsStaticHeaders" rows="3" placeholder='{"Tenant-ID":"north"}'>${escapeHtml(JSON.stringify(c.static_headers || {}, null, 2))}</textarea></div>
          <div><label>Field Mappings JSON</label><textarea id="cmmsFieldMappings" rows="6" placeholder='[{"source":"summary","target":"description","required":true}]'>${escapeHtml(JSON.stringify(c.field_mappings || [], null, 2))}</textarea></div>
          <div><label>Auto-push Note</label><textarea id="cmmsNote" rows="3">${escapeHtml(c.auto_push_note || "")}</textarea></div>
          <div><label>Dry Run Sample JSON</label><textarea id="cmmsDryRunSample" rows="6">${escapeHtml(JSON.stringify({ summary: "Leaking pipe", priority: "High", building: "North", asset_context: { asset_id: "AHU-3" } }, null, 2))}</textarea></div>
          <label><input id="cmmsEnabled" type="checkbox" ${c.enabled ? "checked" : ""}> Enabled</label>
          <label><input id="cmmsAutoPush" type="checkbox" ${c.auto_push_enabled ? "checked" : ""}> Auto-push</label>
          <label><input id="cmmsDryRun" type="checkbox" ${c.dry_run_enabled ? "checked" : ""}> Dry run</label>
          <label><input id="cmmsRequireReview" type="checkbox" ${c.require_metadata_review ? "checked" : ""}> Require metadata review</label>
        </div>
        <div class="command-bar" style="margin-top:12px">
          <button onclick="saveCmmsConnector()">Save</button>
          <button class="secondary" onclick="testCmmsConnector()">Validate</button>
          <button class="secondary" onclick="probeCmmsConnector()">Probe</button>
          <button class="secondary" onclick="previewCmmsConnectorMapping()">Preview Mapped Payload</button>
          <span class="pill ${c.secret_configured ? "ok" : "warning"}">Secret ${c.secret_configured ? "configured" : "missing"}</span>
        </div>
        <pre id="cmmsConnectorOut" style="min-height:80px">${escapeHtml(JSON.stringify(c, null, 2))}</pre>
        <h2 style="margin-top:14px">Recent Push Events</h2>
        <div id="cmmsPushEvents">${renderCmmsPushEvents()}</div>
      </div></div>`;
    }

    function renderCmmsPushEvents() {
      const rows = state.cmmsPushEvents || [];
      if (!rows.length) return `<p class="muted">No CMMS push events recorded for this environment.</p>`;
      return `<table><thead><tr><th>Time</th><th>Status</th><th>Run</th><th>HTTP</th><th>External Ref</th><th>Blocked Reasons</th></tr></thead><tbody>${rows.map(r => `
        <tr><td>${escapeHtml(r.created_at || "")}</td><td><span class="pill ${r.status === "sent" ? "ok" : r.status === "failed" ? "danger" : "warning"}">${escapeHtml(r.status || "")}</span></td><td>${escapeHtml(r.run_id || "")}</td><td>${r.status_code ?? ""}</td><td>${escapeHtml(r.external_reference || "")}</td><td>${escapeHtml((r.blocked_reasons || []).join(", "))}</td></tr>
      `).join("")}</tbody></table>`;
    }

    async function saveCmmsConnector() {
      const secret = $("cmmsSecret").value.trim();
      let staticHeaders = {};
      try {
        staticHeaders = JSON.parse($("cmmsStaticHeaders").value || "{}");
      } catch (e) {
        $("cmmsConnectorOut").textContent = `Invalid Static Headers JSON: ${e.message}`;
        return;
      }
      let fieldMappings = [];
      try {
        fieldMappings = JSON.parse($("cmmsFieldMappings").value || "[]");
      } catch (e) {
        $("cmmsConnectorOut").textContent = `Invalid Field Mappings JSON: ${e.message}`;
        return;
      }
      const payload = {
        enabled: $("cmmsEnabled").checked,
        auto_push_enabled: $("cmmsAutoPush").checked,
        endpoint_url: $("cmmsEndpoint").value.trim(),
        auth_type: $("cmmsAuthType").value,
        auth_header_name: $("cmmsHeaderName").value.trim(),
        timeout_seconds: Number($("cmmsTimeout").value || 5),
        http_method: $("cmmsMethod").value,
        success_status_codes: $("cmmsSuccessCodes").value.trim(),
        external_id_path: $("cmmsExternalPath").value.trim(),
        dry_run_enabled: $("cmmsDryRun").checked,
        require_metadata_review: $("cmmsRequireReview").checked,
        static_headers: staticHeaders,
        payload_root_key: $("cmmsPayloadRoot").value.trim(),
        auto_push_note: $("cmmsNote").value.trim(),
        field_mappings: fieldMappings
      };
      if (secret) payload.secret_value = secret;
      state.cmmsConnector = await api(`/api/admin/environments/${state.selectedEnv}/cmms-connector`, { method: "PUT", body: JSON.stringify(payload) });
      await loadCmmsPushEvents();
      $("cmmsConnectorOut").textContent = JSON.stringify(state.cmmsConnector, null, 2);
      renderEnvironmentTab();
    }

    async function testCmmsConnector() {
      const result = await api(`/api/admin/environments/${state.selectedEnv}/cmms-connector/test`, { method: "POST" });
      $("cmmsConnectorOut").textContent = JSON.stringify(result, null, 2);
    }

    async function probeCmmsConnector() {
      const result = await api(`/api/admin/environments/${state.selectedEnv}/cmms-connector/probe`, { method: "POST" });
      await loadCmmsPushEvents();
      $("cmmsConnectorOut").textContent = JSON.stringify(result, null, 2);
      if ($("cmmsPushEvents")) $("cmmsPushEvents").innerHTML = renderCmmsPushEvents();
    }

    async function previewCmmsConnectorMapping() {
      let canonicalPayload = {};
      try {
        canonicalPayload = JSON.parse($("cmmsDryRunSample").value || "{}");
      } catch (e) {
        $("cmmsConnectorOut").textContent = `Invalid Dry Run Sample JSON: ${e.message}`;
        return;
      }
      const result = await api(`/api/admin/environments/${state.selectedEnv}/cmms-connector/dry-run`, {
        method: "POST",
        body: JSON.stringify({ canonical_payload: canonicalPayload })
      });
      $("cmmsConnectorOut").textContent = JSON.stringify(result, null, 2);
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
        <div class="card"><h2>Contracts</h2><div class="card-body">${tableScroll(renderContractsTable(data))}</div></div>
        <div class="card"><h2>Contract Detail</h2><div class="card-body stack detail-form" id="contractDetail"><p class="muted">Select a contract to view or edit.</p></div></div>
      </div>`, "", "Review output contracts and test schema changes before promotion.");
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
        ${renderReviewerPromptTuningPanel(prompt)}
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

    function renderReviewerPromptTuningPanel(prompt) {
      if (prompt.endpoint !== "cmms-intake-reviewer") return "";
      return `<div class="ai-panel stack">
          <div class="status-line"><h3>Safety Reviewer Smoke Suite</h3><span class="pill">active reviewer prompt</span></div>
          <p class="muted">Creates or runs the reviewer smoke suite using the current intake workflow. Draft reviewer prompts can be tested through admin-only suite runs without changing the live intake API.</p>
          <div class="button-grid"><button class="secondary" onclick="ensureReviewerSmokeSuiteFromPrompt()">Create / Refresh Smoke Suite</button><button onclick="runReviewerSmokeSuiteFromPrompt(${prompt.id})">Run Safety Reviewer Smoke Suite</button><button class="secondary" onclick="compareReviewerPromptAgainstActive(${prompt.id})">Compare Active vs This Prompt</button></div>
          <div id="reviewerSmokeStatus" class="readiness warn"><strong>Smoke suite status</strong><div class="muted">Create or run the suite to see status.</div></div>
          <div id="reviewerPromotionPreview" class="readiness warn"><strong>Promotion preview</strong><div class="muted">Run an active-vs-candidate comparison to prepare an audited override reason if needed.</div></div>
        </div>`;
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

    async function ensureReviewerSmokeSuiteFromPrompt() {
      const env = $("promptEnv")?.value || "DEFAULT";
      const suite = await api("/api/admin/test-suites/safety-reviewer-smoke/ensure", { method: "POST", body: JSON.stringify({ environment_code: env, required_for_promotion: false }) });
      setConsoleOutput("promptResult", suite);
      if ($("reviewerSmokeStatus")) {
        $("reviewerSmokeStatus").className = "readiness";
        $("reviewerSmokeStatus").innerHTML = `<strong>Smoke suite ready</strong><div class="muted">${escapeHtml(suite.name || "Safety Reviewer Smoke Suite")} in ${escapeHtml(suite.environment_code || env)}. Cases: ${(suite.cases || []).length}</div>`;
      }
      return suite;
    }

    async function runReviewerSmokeSuiteFromPrompt(reviewerPromptId) {
      const suite = await ensureReviewerSmokeSuiteFromPrompt();
      const data = await api("/api/admin/test-suites/suite_safety_reviewer_smoke/run", { method: "POST", body: JSON.stringify({ environment_code: suite.environment_code || $("promptEnv")?.value || "DEFAULT", reviewer_prompt_id: reviewerPromptId }) });
      setConsoleOutput("promptResult", data);
      if ($("reviewerSmokeStatus")) {
        const summary = data.summary || {};
        $("reviewerSmokeStatus").className = `readiness ${data.status === "passed" ? "" : data.status === "warning" ? "warn" : "fail"}`;
        $("reviewerSmokeStatus").innerHTML = `<strong>Last run: ${escapeHtml(data.status || "unknown")}</strong><div class="muted">Pass rate: ${summary.pass_rate ?? "n/a"}; passed ${summary.passed ?? 0}/${summary.total ?? 0}; suite run ${escapeHtml(data.suite_run_id || "")}</div>`;
      }
      return data;
    }

    async function compareReviewerPromptAgainstActive(reviewerPromptId) {
      const prompts = await api("/api/admin/prompt-versions/cmms-intake-reviewer");
      const active = prompts.find(p => p.status === "active");
      if (!active) { alert("No active reviewer prompt found."); return; }
      const suite = await ensureReviewerSmokeSuiteFromPrompt();
      const env = suite.environment_code || $("promptEnv")?.value || "DEFAULT";
      const baseline = await api("/api/admin/test-suites/suite_safety_reviewer_smoke/run", { method: "POST", body: JSON.stringify({ environment_code: env, "reviewer_prompt_id": active.id }) });
      const candidate = await api("/api/admin/test-suites/suite_safety_reviewer_smoke/run", { method: "POST", body: JSON.stringify({ environment_code: env, "reviewer_prompt_id": reviewerPromptId }) });
      const comparison = renderReviewerPromptCompareSummary(active, reviewerPromptId, baseline, candidate);
      state.reviewerPromptComparison = comparison;
      setConsoleOutput("promptResult", comparison);
      if ($("reviewerSmokeStatus")) {
        const regressed = comparison.regressed > 0 || comparison.candidate.status === "error";
        $("reviewerSmokeStatus").className = `readiness ${regressed ? "fail" : comparison.candidate.status === "warning" ? "warn" : ""}`;
        $("reviewerSmokeStatus").innerHTML = `<strong>Reviewer prompt comparison: ${regressed ? "regression found" : "no regression"}</strong><div class="muted">Baseline ${escapeHtml(comparison.baseline.status)} vs candidate ${escapeHtml(comparison.candidate.status)}. Passed ${comparison.baseline.passed} -> ${comparison.candidate.passed}.</div>`;
      }
      renderReviewerPromotionPreview(comparison);
      return comparison;
    }

    function renderReviewerPromptCompareSummary(activePrompt, candidatePromptId, baselineRun, candidateRun) {
      const baselineSummary = baselineRun.summary || {};
      const candidateSummary = candidateRun.summary || {};
      const baselinePassed = Number(baselineSummary.passed || 0);
      const candidatePassed = Number(candidateSummary.passed || 0);
      const baselineErrors = Number(baselineSummary.error || 0);
      const candidateErrors = Number(candidateSummary.error || 0);
      const regressed = candidateErrors > baselineErrors || candidatePassed < baselinePassed ? 1 : 0;
      const improved = candidateErrors < baselineErrors || candidatePassed > baselinePassed ? 1 : 0;
      return {
        type: "Reviewer prompt comparison",
        persisted: false,
        baseline: {
          prompt_id: activePrompt.id,
          prompt_version: activePrompt.version,
          suite_run_id: baselineRun.suite_run_id,
          status: baselineRun.status,
          passed: baselinePassed,
          error: baselineErrors,
          pass_rate: baselineSummary.pass_rate ?? null,
        },
        candidate: {
          prompt_id: candidatePromptId,
          suite_run_id: candidateRun.suite_run_id,
          status: candidateRun.status,
          passed: candidatePassed,
          error: candidateErrors,
          pass_rate: candidateSummary.pass_rate ?? null,
        },
        improved,
        regressed,
        unchanged: improved === 0 && regressed === 0,
      };
    }

    function renderReviewerPromotionPreview(comparison) {
      const target = $("reviewerPromotionPreview");
      if (!target) return;
      const regressed = comparison.regressed > 0 || comparison.candidate.status === "error";
      target.className = `readiness ${regressed ? "fail" : ""}`;
      if (regressed) {
        target.innerHTML = `<strong>Promotion preview blocked</strong><div class="muted">Regression or error found in reviewer smoke preview. Do not use override unless a human has reviewed the failure.</div>`;
        return;
      }
      target.innerHTML = `<strong>Preview passed; activation still requires admin override</strong>
        <div class="muted">Reviewer smoke preview found no regression. Use this only to prefill an override reason; the promotion gate remains authoritative.</div>
        <div class="row" style="margin-top:8px"><button class="secondary" onclick="useReviewerPreviewForPromotion()">Use Preview as Override Reason</button></div>`;
    }

    function useReviewerPreviewForPromotion() {
      const comparison = state.reviewerPromptComparison;
      if (!comparison || comparison.regressed > 0 || comparison.candidate.status === "error") {
        alert("Run a reviewer prompt comparison with no regressions first.");
        return;
      }
      const reason = `Reviewer smoke preview passed: baseline suite_run_id ${comparison.baseline.suite_run_id || "n/a"}, candidate suite_run_id ${comparison.candidate.suite_run_id || "n/a"}, no regression. Override used because reviewer prompt comparisons are preview-only in v1.`;
      if ($("promotionOverrideReason")) $("promotionOverrideReason").value = reason;
      if ($("promotionGateResult")) {
        $("promotionGateResult").className = "readiness warn";
        $("promotionGateResult").innerHTML = `<strong>Override reason prepared</strong><div class="muted">${escapeHtml(reason)}</div>`;
      }
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
        <div class="card span-4"><h2>Generate key</h2><div class="card-body stack">
          <label>Name</label><input id="kName" value="external-tester">
          <label>Allowed endpoints</label><textarea id="kAllowedEndpoints" rows="4" placeholder="cmms-intake, summarize-work-order, extract-work-order-fields, cmms-assistant, intake/email">cmms-intake</textarea>
          <div class="muted">Blank means all controlled AI endpoints.</div>
          <label>Allowed environments</label><input id="kAllowedEnvironments" value="DEFAULT" placeholder="DEFAULT, TEST">
          <div class="muted">Blank means all environments.</div>
          <button onclick="createKey()">Generate</button>
        </div></div>
        <div class="card span-8"><h2>Keys</h2><div class="card-body">${tableScroll(renderApiKeyTable(data))}</div></div>
        <div class="card span-12"><h2>Generated key output</h2><pre id="kOut">{}</pre></div>
      </div>`, "", "Manage generated API keys and keep scoped access visible.");
    }
    function csvList(value) {
      return String(value || "").split(/[,\n]/).map(v => v.trim()).filter(Boolean);
    }
    function scopeLabel(values) {
      const list = Array.isArray(values) ? values : [];
      return list.length ? list.map(v => `<span class="pill">${escapeHtml(v)}</span>`).join(" ") : '<span class="muted">All</span>';
    }
    function renderApiKeyTable(rows) {
      if (!rows || !rows.length) return "<p class='muted'>No records.</p>";
      return `<table><thead><tr><th>Key</th><th>Name</th><th>Status</th><th>Endpoints</th><th>Environments</th><th>Usage</th><th>Last Used</th><th>Action</th></tr></thead><tbody>${rows.map(r => `<tr>
        <td>${escapeHtml(r.key_id)}</td>
        <td>${escapeHtml(r.name)}</td>
        <td><span class="pill ${r.enabled ? "ok" : "danger"}">${r.enabled ? "enabled" : "disabled"}</span></td>
        <td>${scopeLabel(r.allowed_endpoints)}</td>
        <td>${scopeLabel(r.allowed_environments)}</td>
        <td>${r.usage_count ?? 0}</td>
        <td>${escapeHtml(r.last_used_at || "")}</td>
        <td><button class="danger" onclick="disableKey('${escapeAttr(r.key_id)}')">Disable</button></td>
      </tr>`).join("")}</tbody></table>`;
    }
    async function createKey() {
      const data = await api("/api/admin/api-keys", {
        method: "POST",
        body: JSON.stringify({
          name: $("kName").value,
          allowed_endpoints: csvList($("kAllowedEndpoints").value),
          allowed_environments: csvList($("kAllowedEnvironments").value)
        })
      });
      await keys();
      $("kOut").textContent = JSON.stringify(data, null, 2);
    }
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
        <div class="card span-12"><h2>Workflow Run Detail</h2><div class="card-body" id="logTraceDetail"><span class="muted">Select View Run from a workflow run.</span></div></div>
        <div class="card span-12"><h2>Runtime log</h2><pre>${data.lines.join("\n")}</pre></div>
      </div>`);
    }

    function renderWorkflowRunsTable(rows) {
      if (!rows.length) return '<p class="muted">No workflow runs recorded yet.</p>';
      return `<table><thead><tr><th>Run ID</th><th>Endpoint</th><th>Environment</th><th>Status</th><th>Duration</th><th>Started</th><th>Source</th><th>Actions</th></tr></thead><tbody>${rows.map(r => `
        <tr><td><strong>${escapeHtml(r.run_id)}</strong></td><td>${escapeHtml(r.endpoint)}</td><td>${escapeHtml(r.environment_code || "")}</td><td><span class="pill ${r.status === "failed" ? "danger" : r.status === "completed_with_warnings" ? "warning" : "ok"}">${escapeHtml(r.status)}</span></td><td>${r.duration_ms ?? ""} ms</td><td>${escapeHtml(r.started_at || "")}</td><td>${escapeHtml(r.source || "")}</td><td><button class="secondary" onclick="viewWorkflowTrace('${escapeAttr(r.run_id)}')">View Run</button></td></tr>`).join("")}</tbody></table>`;
    }

    async function viewWorkflowTrace(runId) {
      const trace = await api(`/api/admin/workflow-runs/${runId}`);
      state.lastWorkflowTrace = trace;
      $("logTraceDetail").innerHTML = renderWorkflowTrace(trace);
    }
    async function reports() { const data = await api("/api/admin/reports/usage"); pageShell("Reports", `<div class="card"><h2>Usage</h2><div class="card-body">${table(data, ["endpoint","status_code","key_name","environment_code","calls","avg_duration_ms"])}</div></div>`); }
    async function kb() { const data = await api("/api/kb/status"); pageShell("Knowledge Base", `<div class="card"><h2>Future KB interface</h2><div class="card-body"><pre>${JSON.stringify(data, null, 2)}</pre></div></div>`); }
    async function remote() { const data = await api("/api/admin/settings/remote_access_url").catch(()=>({ value:"" })); pageShell("Remote Access", `<div class="card"><h2>Remote link notes</h2><div class="card-body stack"><input id="remoteUrl" value="${data.value||""}" placeholder="https://example.trycloudflare.com"><button onclick="saveRemote()">Save</button><p class="muted">Cloudflare is still started manually. Store the URL here for reference.</p></div></div>`); }
    async function saveRemote() { await api("/api/admin/settings/remote_access_url", { method: "PATCH", body: JSON.stringify({ value: $("remoteUrl").value }) }); remote(); }
    async function setupWizard() {
      pageShell("Setup Wizard", `<div class="grid">
        <div class="card span-8"><h2>Checklist</h2><div class="card-body" id="setupStatus"><p class="muted">Loading checks...</p></div></div>
        <div class="card span-4"><h2>Backup</h2><div class="card-body stack">
          <button class="secondary" onclick="refreshSetupStatus()">Refresh Checks</button>
          <button onclick="createSystemBackup()">Create Backup</button>
          <button class="secondary" onclick="downloadLatestBackupManifest()">Download Latest Backup Manifest</button>
          <pre id="backupResult">{}</pre>
        </div></div>
        <div class="card span-12"><h2>Backups</h2><div class="card-body" id="setupBackups"><p class="muted">Loading backups...</p></div></div>
      </div>`);
      await refreshSetupStatus();
      await refreshBackups();
    }

    async function refreshSetupStatus() {
      const target = $("setupStatus");
      if (target) target.innerHTML = '<p class="muted">Refreshing checks...</p>';
      try {
        const data = await api("/api/admin/setup/status");
        state.setupStatus = data;
        if (target) target.innerHTML = renderSetupChecks(data);
      } catch (e) {
        if (target) target.innerHTML = `<div class="pill danger">Failed</div><pre>${JSON.stringify(e.data || { detail: e.message }, null, 2)}</pre>`;
      }
    }

    async function refreshBackups() {
      const target = $("setupBackups");
      if (target) target.innerHTML = '<p class="muted">Refreshing backups...</p>';
      try {
        state.backups = await api("/api/admin/system/backups");
        if (target) target.innerHTML = renderSetupBackups(state.backups);
      } catch (e) {
        if (target) target.innerHTML = `<div class="pill danger">Failed</div><pre>${JSON.stringify(e.data || { detail: e.message }, null, 2)}</pre>`;
      }
    }

    async function createSystemBackup() {
      const result = $("backupResult");
      if (result) result.textContent = "Creating backup...";
      try {
        const backup = await api("/api/admin/system/backup", { method: "POST" });
        if (result) result.textContent = JSON.stringify({ backup_id: backup.backup_id, file_name: backup.file_name, size_bytes: backup.size_bytes }, null, 2);
        await refreshBackups();
        await refreshSetupStatus();
      } catch (e) {
        if (result) result.textContent = JSON.stringify(e.data || { detail: e.message }, null, 2);
      }
    }

    function renderSetupChecks(data) {
      const items = data?.items || [];
      if (!items.length) return '<p class="muted">No setup checks returned.</p>';
      return `<div class="stack">
        <div class="row"><span class="pill ${statusClass(data.overall_status)}">${escapeHtml(statusLabel(data.overall_status))}</span><span class="muted">${escapeHtml(data.checked_at || "")}</span></div>
        ${tableScroll(`<table><thead><tr><th>Check</th><th>Status</th><th>Detail</th><th>Recommended action</th></tr></thead><tbody>${items.map(item => `
          <tr>
            <td><strong>${escapeHtml(item.label)}</strong></td>
            <td><span class="pill ${statusClass(item.status)}">${escapeHtml(statusLabel(item.status))}</span></td>
            <td>${escapeHtml(item.detail || "")}</td>
            <td>${escapeHtml(item.recommended_action || "")}</td>
          </tr>`).join("")}</tbody></table>`)}
      </div>`;
    }

    function renderSetupBackups(backups) {
      if (!backups || !backups.length) return '<p class="muted">No backups created yet.</p>';
      return tableScroll(`<table><thead><tr><th>Created</th><th>Backup</th><th>Size</th><th>Mode</th></tr></thead><tbody>${backups.map(backup => `
        <tr>
          <td>${escapeHtml(backup.created_at || "")}</td>
          <td><strong>${escapeHtml(backup.file_name || backup.backup_id || "")}</strong></td>
          <td>${escapeHtml(formatBytes(backup.size_bytes || 0))}</td>
          <td>${escapeHtml(backup.manifest?.restore?.mode || "preview_only")}</td>
        </tr>`).join("")}</tbody></table>`);
    }

    function statusClass(status) {
      if (status === "passed") return "ok";
      if (status === "failed") return "danger";
      return "";
    }

    function statusLabel(status) {
      return ({ passed: "Passed", warning: "Warning", failed: "Failed", not_checked: "Not checked" })[status] || "Not checked";
    }

    function formatBytes(value) {
      const size = Number(value || 0);
      if (size < 1024) return `${size} B`;
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
      return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    }

    function downloadLatestBackupManifest() {
      const backup = (state.backups || [])[0];
      if (!backup?.manifest) { alert("No backup manifest available."); return; }
      const blob = new Blob([JSON.stringify(backup.manifest, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${backup.backup_id || "backup"}-manifest.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }
    async function system() {
      pageShell("System", `<div class="grid"><div class="card span-6"><h2>Status</h2><div class="card-body stack"><label>Local control API key</label><input id="systemKey" type="password" value="${escapeAttr(state.systemControlKey)}" placeholder="Paste generated API key"><button class="secondary" onclick="loadSystemStatus()">Refresh Status</button><pre id="systemStatusOut">{ "status": "Local system controls require an API key and admin session." }</pre></div></div>
      <div class="card span-6"><h2>Local-only controls</h2><div class="card-body row"><button onclick="systemApi('/api/system/ollama/start',{method:'POST'}).then(loadSystemStatus)">Start Ollama</button><button class="secondary" onclick="systemApi('/api/system/ollama/stop',{method:'POST'}).then(loadSystemStatus)">Stop Ollama</button><button class="danger" onclick="systemApi('/api/system/shutdown',{method:'POST'})">Stop API</button></div></div></div>`);
    }

    function systemHeaders() {
      state.systemControlKey = $("systemKey")?.value || state.systemControlKey || "";
      return { "x-api-key": state.systemControlKey };
    }

    async function systemApi(path, opts = {}) {
      return api(path, { ...opts, headers: { ...systemHeaders(), ...(opts.headers || {}) } });
    }

    async function loadSystemStatus() {
      const target = $("systemStatusOut");
      if (!target) return;
      try {
        const s = await systemApi("/api/system/status");
        target.textContent = JSON.stringify(s, null, 2);
      } catch (e) {
        target.textContent = JSON.stringify(e.data || { detail: e.message }, null, 2);
      }
    }
    function table(rows, cols, action) {
      if (!rows || !rows.length) return "<p class='muted'>No records.</p>";
      return `<table><thead><tr>${cols.map(c=>`<th>${c}</th>`).join("")}${action?"<th>Action</th>":""}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${r[c] ?? ""}</td>`).join("")}${action?`<td><button class="danger" onclick="${action}('${r.key_id}')">Disable</button></td>`:""}</tr>`).join("")}</tbody></table>`;
    }
    registerOfflineShell();
    boot();
  </script>
</body>
</html>"""



def render_portal_html() -> str:
    return PORTAL_HTML
