# Local CMMS LLM API

## Overview
This repository contains a local, Windows-friendly wrapper API for controlled CMMS work order intake using a local Ollama LLM model.

The service is designed to provide AI-assisted summaries, field extraction, validation, and draft generation for facility management requests. It intentionally does not perform any write operations to a CMMS system, create work orders, approve requests, or send email messages.

## Key Features

- Local AI inference using `Ollama` and the `qwen3:8b` model
- FastAPI-based HTTP API with AI advisory endpoints
- Secure API access through `x-api-key`
- Built-in operator UI available at `/ui`
- Deterministic intake workflow with classifier, extractor, validator, and draft generator agents
- Clear separation of AI suggestion from actual CMMS write-back

## Requirements

- Windows 10/11
- Python 3.11+ recommended
- Ollama installed and configured
- `qwen3:8b` model available in Ollama

## Installation

1. Create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Ensure Ollama is installed and the model is available:

```powershell
ollama --version
ollama pull qwen3:8b
```

## Configuration

Set a local AI API key before starting the service.

```powershell
$env:LLM_API_KEY="your-secret-key"
```

Optional environment settings for portal admin access:

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="your-admin-password"
```

## Running the API

Start the FastAPI service directly:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Recommended Startup

Use the provided launcher scripts for convenience:

```powershell
.\Start-CMMS-LLM-API.ps1
```

Or use the batch script on Windows:

```text
Start-CMMS-LLM-API.bat
```

These scripts help with environment creation, dependency installation, and starting the API.

## API Endpoints

### GET /health

Checks service status. No API key required.

Response example:

```json
{
  "status": "ok",
  "service": "local-cmms-llm-api",
  "model": "qwen3:8b"
}
```

### POST /api/ai/summarize-work-order

Creates a concise summary from raw intake text.

Header:

```text
x-api-key: your-api-key
```

Request body example:

```json
{
  "text": "The air conditioner in ARC room 205 is making loud noise."
}
```

### POST /api/ai/extract-work-order-fields

Extracts structured fields such as building, room, and priority.

Header:

```text
x-api-key: your-api-key
```

Request body example:

```json
{
  "text": "The air conditioner in ARC room 205 is making loud noise and the room is too warm.",
  "valid_buildings": ["ARC", "CAMPUSVIEW", "ZONE-18"],
  "valid_priorities": ["LOW", "NORMAL", "URGENT"]
}
```

### POST /api/ai/cmms-intake

Runs the full intake workflow with classifier, field extractor, validator, and draft generator agents.

Header:

```text
x-api-key: your-api-key
```

This endpoint is intended to produce advisory output only.

### GET /ui

Opens the local operator console for manual review and management.

```text
http://127.0.0.1:8000/ui
```

## Testing

Run the local API test script:

```powershell
.\test_api.ps1
```

## Security and Safety Notes

- The AI layer is advisory only.
- No direct CMMS updates are performed by the service.
- Human review is required before any real work order creation.
- Do not expose Ollama's internal port directly; only expose the FastAPI wrapper if needed.

## Project Goals

This project provides a safe, local AI assistant for CMMS intake workflows. It is built to keep machine intelligence under control and preserve auditability by separating suggestion from execution.

The UI calls only the controlled advisory endpoints. It is not a generic chat interface.

The UI also includes a local process log panel and local-only controls for:

- Checking service/Ollama status.
- Viewing recent log lines.
- Generating named API keys.
- Disabling generated API keys.
- Starting Ollama if it is stopped.
- Stopping Ollama.
- Stopping the FastAPI service.

System control endpoints require an authenticated admin portal session and are restricted to local requests from `127.0.0.1` or `::1`.
API key generation, disabling, user management, environment management, and process controls require an admin portal session.

## Logs

Runtime logs are written to:

```text
logs/cmms-llm-api.log
```

The API logs:

- Service startup and shutdown.
- API calls with method, path, status, duration, and client IP.
- API calls by `key_id` and key name.
- Ollama start/stop requests from the local UI.

The API does not log API keys.

## API keys

The environment variable `LLM_API_KEY` is a compatibility API key for direct AI endpoint calls only.
It must not be used for portal administration and cannot access `/api/admin/*`.
Generated API key records are stored in SQLite:

```text
data/portal.db
```

Generated keys:

- Are shown only once when created.
- Must be copied from the `api_key` field, not the `key_id` field.
- Are stored as SHA-256 hashes, not plaintext.
- Can be disabled from the local UI.
- Can call the controlled AI endpoints while enabled.
- Cannot access admin endpoints.
- Are logged by `key_id` and name for usage tracking.

Do not commit `api_keys.json`.

## Environments

Admin users can create environment codes in the portal. API calls can pass:

```json
{
  "environment_code": "DEFAULT",
  "text": "The air conditioner in ARC room 205 is making loud noise."
}
```

When `environment_code` is provided, the API loads buildings, rooms, priorities, work order types, assignment values, employee numbers, and job types from the saved environment configuration.

The older `valid_buildings` and `valid_priorities` request shape still works for compatibility.

## Quick Start Examples

### Summary example

```powershell
curl -X POST "http://127.0.0.1:8000/api/ai/summarize-work-order" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"text": "The air conditioner in ARC room 205 is making loud noise and the room is too warm."}'
```

Expected response:

```json
{
  "summary": "Air conditioner in ARC room 205 is making loud noise and the room is too warm."
}
```

### Field extraction example

```powershell
curl -X POST "http://127.0.0.1:8000/api/ai/extract-work-order-fields" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"text": "The air conditioner in ARC room 205 is making loud noise and the room is too warm.", "valid_buildings": ["ARC", "CAMPUSVIEW", "ZONE-18"], "valid_priorities": ["LOW", "NORMAL", "URGENT"]}'
```

Expected response structure:

```json
{
  "building": "ARC",
  "room": "205",
  "priority": "NORMAL",
  "issue": "Air conditioner making loud noise and room too warm"
}
```

### CMMS intake workflow example

```powershell
curl -X POST "http://127.0.0.1:8000/api/ai/cmms-intake" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"text": "The air conditioner in ARC room 205 is making loud noise and the room is too warm."}'
```

This endpoint returns advisory output only and may include classification, extracted fields, validation details, and a draft work order description.

## FAQ

### What is the difference between `/api/ai/cmms-intake` and `/api/ai/extract-work-order-fields`?

`/api/ai/extract-work-order-fields` returns structured field extraction from text only. `/api/ai/cmms-intake` runs the full intake workflow, including classification, validation, and draft generation.

### Can this service create actual CMMS work orders?

No. The service is intentionally advisory only. It does not write to any CMMS database, create work orders, approve requests, or send emails.

### Do I need a live internet connection?

No, as long as `Ollama` and the `qwen3:8b` model are installed locally. The API itself is hosted on your machine.

### How should I protect the API?

Only run the service on trusted local hardware. Use `x-api-key` for endpoint authentication, and do not expose `http://127.0.0.1:8000` directly to untrusted networks without a secure proxy.

### Where are API keys stored?

Generated keys are stored in `data/portal.db` as hashed values. The compatibility key from `LLM_API_KEY` is not stored in the portal database.
