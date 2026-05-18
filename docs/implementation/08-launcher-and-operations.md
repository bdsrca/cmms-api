# 08 - Launcher And Operations

The Windows launcher still provides one-click startup:

```powershell
.\Start-CMMS-LLM-API.ps1
```

The launcher requires portal admin credentials before startup:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

It rejects the old `change-this-password` placeholder and short passwords.

`LLM_API_KEY` can still default to `my-secret-key` for local AI endpoint compatibility, but it is not a portal admin credential.

The launcher still checks Python dependencies, starts Ollama when needed, verifies `qwen3:8b`, starts FastAPI, and opens `/ui`.

Cloudflare Tunnel remains manual.
