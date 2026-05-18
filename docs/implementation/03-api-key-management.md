# 03 - API Key Management

Generated API keys are now stored in SQLite instead of relying on `api_keys.json`.

Only key hashes are stored. The plaintext key is returned once during generation.

The environment variable `LLM_API_KEY` remains a compatibility API key for AI endpoints only.
It does not grant access to `/api/admin/*`, user management, API key management, environment management, or system controls.

Generated API keys also call AI endpoints only by default. Portal administration requires session login.

Tracked metadata:

- Key id
- Name
- Owner
- Enabled/disabled state
- Usage count
- Last used timestamp

Disabled keys return `401`.
