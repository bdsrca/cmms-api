# Test Case From Run v2 and API Docs Export

## Purpose

Connect workflow observability to regression testing, and make endpoint usage easier to share without exposing runtime secrets.

## Workflow Run To Test Case

- Workflow Run Detail now opens an editable modal for creating a test case.
- The modal includes:
  - name
  - endpoint
  - environment
  - editable expected JSON
  - tags
  - notes
- The backend now generates a clean expected JSON template from the actual run response when no custom expected JSON is supplied.
- The template includes core assertions only:
  - summary_contains
  - building
  - room
  - priority
  - work_order_type
  - assign_to
  - issue_to
  - job_type
  - contract_valid
  - environment_valid
  - expected_errors
  - expected_warnings

## API Docs Export

- API Builder now includes an API Documentation panel.
- Operators can copy or download a public-safe Markdown package.
- The exported text documents:
  - API key authentication
  - environment code usage
  - controlled AI endpoints
  - readiness checks
  - CMMS safety boundaries

## Safety

- No database schema change was added.
- No new LLM call was added.
- No generic chat endpoint was added.
- No autonomous router or LLM judge was added.
- No CMMS push behavior was changed.
- No email sending behavior was added.
- The docs export does not include secrets, API keys, cookies, databases, logs, or runtime state.

## Verification

- Added a backend test for clean expected JSON generation.
- Added UI tests for the workflow-run test case modal and API docs export controls.
