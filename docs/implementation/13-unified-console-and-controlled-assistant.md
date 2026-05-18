# Unified Console and Controlled Assistant

## Purpose

The Test Console now uses one editable input for both typed text and browser voice transcript. Voice recognition writes into the same textarea that the operator can review and edit before calling the API.

## Controlled Assistant Mode

A new controlled endpoint was added:

```text
POST /api/ai/cmms-assistant
```

This is not a generic `/chat` endpoint. It is restricted to CMMS intake, validation, API usage, troubleshooting, and advisory drafting help.

The assistant returns JSON:

```json
{
  "mode": "cmms-assistant",
  "response": "string",
  "model": "qwen3:8b",
  "safety": {
    "advisory_only": true,
    "cmms_write_back": false,
    "work_order_created": false,
    "email_sent": false
  }
}
```

## Safety Boundary

The assistant cannot:

- write to CMMS
- create work orders
- approve requests
- send emails
- bypass authentication
- expose secrets

## UI Fix

The AI Output Contracts page now uses a wider responsive detail panel. This prevents the contract editor fields and schema textarea from collapsing into an unusable narrow column on medium-width screens.
