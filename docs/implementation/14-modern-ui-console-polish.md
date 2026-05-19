# Modern UI and Console Polish

## Purpose

This step updates the portal visual layer and Test Console ergonomics without changing the existing CMMS validation pipeline or database schema.

## Visual Direction

The portal now uses a Linear/OpenAI-inspired SaaS admin style:

- light neutral background
- rounded controls
- soft borders and focus rings
- modern buttons, inputs, selects, checkboxes, cards, tables, modals, and command bars
- narrower left navigation with icons
- red admin-only markers

AI/API execution surfaces keep a Replicate-style developer feel:

- dark code/result panels
- JSON output blocks
- generated API examples
- Test Console result areas
- Output Contract sample validation output

## Console Output Tools

Console-style outputs now support:

- Pretty/raw JSON toggle
- Copy
- Download

Applied to:

- Test Console extracted JSON
- API Builder generated examples/live response
- Output Contract sample validation result

## Voice Intake

Voice intake now writes into the same editable request textarea used for text input.

The voice panel was simplified to:

- language selector
- Start Listening
- Stop
- browser support/fallback message
- privacy note

Speech recognition stops automatically after 5 seconds without detected speech.

## Default API Key

After login, the UI calls an authenticated helper route:

```text
GET /api/default-api-key
```

This fills API key fields from `LLM_API_KEY` for local operator convenience. Existing API key auth behavior remains unchanged.

## Layout Fixes

AI Output Contracts now uses a vertical full-width layout:

- Contracts table on top
- Contract detail/editor below

This avoids narrow detail controls on medium-width screens.

## Safety

Existing CMMS safety boundaries remain unchanged:

- no CMMS writes
- no automatic work order creation
- no automatic emails
- no generic `/chat` route
- advisory mode only
