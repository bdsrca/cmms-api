# Canonical CMMS Payload Preview Design

## Goal

Add a generic CMMS work order payload preview to the existing reviewed handoff
candidate flow. The preview gives operators and later CMMS adapters a stable,
review-gated projection without writing to a CMMS.

## Scope

The existing admin-only handoff candidate remains the source response for this
slice. The server adds a `cmms_payload_preview` object to that candidate after a
metadata review has been applied.

This slice does not add a CMMS write endpoint, a vendor-specific adapter, or a
configuration UI for mapping fields.

## Chosen Approach

Keep the existing handoff candidate endpoint and add a pure mapping projection
inside its response.

This is the smallest path that preserves the current review gate and workflow
trace UI. A separate preview endpoint would duplicate the same gate today, and
environment-configured vendor mappings should wait until a target CMMS schema is
known.

## Response Shape

The existing candidate response keeps its current fields and gains:

```json
{
  "cmms_payload_preview": {
    "schema": "canonical_cmms_work_order_v1",
    "fields": {
      "summary": "Air conditioner in ARC room 205 is making loud noise.",
      "location": {
        "building": "ARC",
        "room": "205"
      },
      "priority": "NORMAL",
      "work_order_type": "HVAC",
      "assignment": {
        "assign_to": null,
        "issue_to": null,
        "job_type": null
      },
      "requester": {
        "name": "Leon",
        "email": "bdsrca@gmail.com",
        "phone": "1234"
      },
      "requested_due_date": "2026-05-25",
      "source": {
        "method": "email",
        "submitted_at": "2026-05-22T14:30:00Z",
        "intake_run_id": "run_123"
      }
    }
  }
}
```

The canonical preview maps from the existing candidate `payload`:

| Candidate payload | Canonical preview |
| --- | --- |
| `summary` | `fields.summary` |
| `building`, `room` | `fields.location` |
| `priority` | `fields.priority` |
| `work_order_type` | `fields.work_order_type` |
| `assign_to`, `issue_to`, `job_type` | `fields.assignment` |
| `submitted_by`, `submitted_email`, `submitted_phone` | `fields.requester` |
| `requested_due` | `fields.requested_due_date` |
| `submitted_method`, `submitted_at`, candidate `run_id` | `fields.source` |

## Components

`app/intake_handoff.py` owns the pure canonical mapping helper and attaches the
preview while building the existing handoff candidate.

`app/operations_routes.py` keeps the existing admin route and review gate. The
route returns the richer candidate response without adding another endpoint.

`app/ui.py` keeps the existing `CMMS Candidate` trace action. Because the UI
already renders the full candidate JSON, the new preview appears in that panel.

## Safety And Errors

The preview inherits the candidate endpoint gate:

- callers must have an authenticated admin portal session;
- the workflow run must exist;
- the run must have an applied intake metadata review;
- the run must include persisted extraction fields needed for a candidate.

The preview is advisory data only. Existing candidate safety flags continue to
state that no CMMS write-back occurred and no work order was created.

## Testing

Tests cover the canonical projection from a reviewed candidate, the continued
review gate on the existing route, and the presence of requester, due date, and
location fields in the preview.
