# 04 - Environments And Code Lists

Environments are saved by `environment_code`, display name, and enabled state.

The portal treats Environment as the primary resource. Code Lists belong to an Environment detail page rather than being a thin top-level page.

Supported code categories:

- buildings
- rooms
- priorities
- work_order_types
- assign_to
- issue_to_employee_number
- job_type
- custom future categories using `custom:<name>`

AI endpoints accept `environment_code`. When supplied, the server loads saved code lists and uses them for validation. Existing request bodies with `valid_buildings` and `valid_priorities` remain supported.

Code list rows support:

- Code
- Description
- Aliases
- Metadata JSON
- Enabled/disabled status
- Source
- Updated timestamp

Imports use a preview-first workflow. The preview reports valid rows, duplicates, invalid rows, existing rows that will be updated, and new rows that will be inserted.
