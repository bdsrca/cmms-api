# 05 - Portal UI

`GET /ui` now serves an Azure-style management portal.

The shell includes:

- Login page
- Top command bar
- Left navigation
- Role-aware admin menu visibility
- Dashboard
- Test Console
- API Call Builder
- Environments
- API Keys
- Users
- Logs
- Reports
- Knowledge Base
- Remote Access
- System

The UI remains plain HTML/CSS/JavaScript served by FastAPI to preserve one-click Windows startup.

Current resource-model direction:

- Environment is the primary resource.
- Code Lists are managed inside the Environment detail page.
- Code Lists use an Azure-style command bar, resource context, table/grid, right-side detail blade, and import modal.
- Runtime/log output uses terminal styling only where it is actually log-like.
