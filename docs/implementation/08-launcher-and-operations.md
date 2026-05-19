# 08 - Launcher And Operations

The Windows launcher still provides one-click startup:

```powershell
.\Start-CMMS-LLM-API.ps1
```

The launcher requires portal admin credentials before startup:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `LLM_API_KEY`

It rejects the old `change-this-password` placeholder and short passwords.

`LLM_API_KEY` no longer defaults to `my-secret-key` during one-click startup. Startup fails when it is missing, because generated artifacts and demos must not rely on a shared default API key.

The launcher still checks Python dependencies, starts Ollama when needed, verifies `qwen3:8b`, starts FastAPI, and opens `/ui`.

Cloudflare Tunnel remains manual.
