# Metadata Review Apply API Plan

## Scope

Persist extracted intake metadata per CMMS intake run and expose an admin-only
review/apply endpoint that updates only reviewable metadata fields.

## Files

- `tests/test_metadata_review_apply_api.py`: cover patch merge/correction logic
  and API/storage wiring.
- `app/intake_metadata_reviews.py`: own review record storage and review patch
  application.
- `app/db.py`: add the persisted review record table and index.
- `app/ai_endpoints.py`: save each intake run's extracted metadata review record.
- `app/operations_routes.py`: expose the admin review/apply endpoint and payload
  model.
- `app/ui.py`: call the controlled API from the metadata review Apply action.

## Tasks

1. Add failing tests for the review patch helper and source-level route/table/UI
   integration points.
2. Implement persisted review records and deterministic patch application with
   `reviewed` provenance and corrected field paths.
3. Register the admin review/apply endpoint and save extracted metadata for
   intake runs.
4. Update the operator UI Apply action to post the reviewed fields to the API
   and render the confirmed server response.
5. Run focused tests, the full test suite, and compile checks.
