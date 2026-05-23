# Environment Handoff Preview Design

## Goal

Add an environment-scoped handoff preview to the reviewed CMMS candidate response.
The preview shows whether the canonical CMMS payload is ready for a configured
environment without writing to a CMMS or introducing a vendor-specific adapter.

## Scope

The existing admin-only, metadata-review-gated handoff candidate endpoint remains
the only API entry point for this slice. The server adds an
`environment_handoff_preview` object to the candidate when an `environment_code`
is present on the workflow run.

This slice does not add a CMMS write endpoint, auto-submit behavior, or a
vendor-specific outbound schema.

## Chosen Approach

Append an environment-aware preview to the existing handoff candidate response.
This keeps the current review gate, safety flags, and trace UI path intact while
making the next handoff state explicit.

A separate endpoint would duplicate the same gating logic today. Folding the
environment result into `cmms_payload_preview` would blur the difference between
the stable canonical schema and environment-specific readiness.

## Response Shape

The reviewed candidate keeps its current fields and gains:

```json
{
  "environment_handoff_preview": {
    "schema": "environment_cmms_handoff_v1",
    "environment_code": "DEFAULT",
    "status": "needs_review",
    "fields": {
      "summary": "Air conditioner is too warm.",
      "building": "ARC",
      "room": "207",
      "priority": "NORMAL",
      "work_order_type": "HVAC",
      "assign_to": null,
      "issue_to": null,
      "job_type": null,
      "requester_name": "Leon",
      "requester_email": "leon@example.com",
      "requester_phone": "416-555-0199",
      "requested_due_date": "2026-05-25",
      "source_method": "email_api",
      "intake_run_id": "run_123"
    },
    "validation": {
      "valid": false,
      "missing_fields": [],
      "errors": [],
      "warnings": [
        "Room 207 is not in configured room codes.",
        "Assign To is empty."
      ],
      "normalized": {
        "building": "ARC",
        "priority": "NORMAL",
        "work_order_type": "HVAC"
      }
    }
  }
}
```

## Field Mapping

The environment preview maps from `cmms_payload_preview.fields` into a flat
outbound handoff shape:

| Canonical preview | Environment handoff field |
| --- | --- |
| `summary` | `summary` |
| `location.building` | `building` |
| `location.room` | `room` |
| `priority` | `priority` |
| `work_order_type` | `work_order_type` |
| `assignment.assign_to` | `assign_to` |
| `assignment.issue_to` | `issue_to` |
| `assignment.job_type` | `job_type` |
| `requester.name` | `requester_name` |
| `requester.email` | `requester_email` |
| `requester.phone` | `requester_phone` |
| `requested_due_date` | `requested_due_date` |
| `source.method` | `source_method` |
| `source.intake_run_id` | `intake_run_id` |

## Validation

The preview should reuse the existing environment validation semantics for CMMS
code fields. It should check configured values for building, room, priority,
work order type, assign to, issue to, and job type when an enabled environment
exists.

The first version must not auto-fill `assign_to`, `issue_to`, or `job_type` from
environment defaults. Empty values remain empty and appear as warnings when the
field is optional but useful for handoff.

## Status Rules

`status` is derived from validation:

- `ready`: no errors, no warnings, and the environment is enabled.
- `needs_review`: no blocking errors, but warnings or optional handoff fields
  need operator attention.
- `blocked`: the environment is missing or disabled, required validation fails,
  or the candidate lacks a usable canonical preview.

## Components

`app/intake_handoff.py` owns the pure mapping helper that converts canonical
preview fields into the flat environment handoff preview.

The helper should call existing environment value accessors or validation logic
rather than adding a separate code-list query path.

`app/operations_routes.py` keeps the current candidate route and review gate.
The route returns the enriched candidate response.

`app/ui.py` does not need a new control for the first version because the trace
panel already renders the full candidate JSON.

## Safety And Errors

The preview inherits the existing candidate safety boundary:

- admin portal session required;
- workflow run must exist;
- intake metadata review must already be applied;
- persisted extraction fields must be present;
- no CMMS write-back occurs;
- no work order is created.

If environment validation cannot run because the environment is absent or
disabled, the candidate response should still return with
`environment_handoff_preview.status` set to `blocked` and a validation error
explaining the environment problem.

## Testing

Tests should cover:

- reviewed candidates include `environment_handoff_preview` when the run has an
  environment code;
- the preview maps requester, due date, source, assignment, and location fields;
- an unknown room or empty assignment field produces `needs_review`;
- missing or disabled environment produces `blocked`;
- the existing admin-only and metadata-review gate remains unchanged.
