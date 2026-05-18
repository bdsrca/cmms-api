# Console, Code List, and API Builder Polish

## Purpose

This step fixes the first usability bugs found in the management portal and tightens the visual direction:

- IBM / Carbon-style shell for navigation, resources, forms, tables, and admin pages.
- Replicate-style execution panels for AI playground surfaces, JSON output, voice demo, and generated API calls.

The intent is to keep enterprise resource management calm and structured while making AI execution surfaces feel code-forward and easy to test.

## Fixed Issues

1. Test Console now has a more visible `Text / Voice` segmented control inside the request panel.
2. Code Lists can read a local CSV file into the import modal before preview/import.
3. Code List category changes reload the environment code data and re-render the table/detail blade.
4. API Call Builder now generates richer PowerShell and curl examples, expected response fields, endpoint notes, and optional readiness logic.
5. API Call Builder can run a live call and show whether the response has enough validated information for a human-controlled work order workflow.

## CSV Import

CSV upload is browser-side only. The browser reads the selected file as text and sends the same existing import payload to the backend:

```json
{
  "category": "buildings",
  "text": "ARC, ARC Building\nCAMPUSVIEW, Campus View",
  "replace": false
}
```

No new upload endpoint was added.

## Readiness Validation

For `cmms-intake`, readiness uses existing response fields:

- `contract.valid`
- `ai_validation.valid`
- `validation.can_create_work_order`
- `validation.missing_fields`

The UI remains advisory only. It does not create work orders.

## Visual Direction

Global shell and resource areas follow an IBM / Carbon-inspired structure: dark shell, blue accent, flat panels, dense tables, and restrained forms.

AI execution surfaces use a Replicate-inspired treatment: clean white playground panels, code-forward dark JSON/code blocks, and direct run/response feedback.
