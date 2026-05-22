# Metadata Review Provenance Plan

## Scope

Carry the existing operator review shape through CMMS intake API responses and the
default output contract without reintroducing customer-supplied metadata inputs.

## Files

- `tests/test_intake_metadata.py`: cover default review state and contract shape.
- `app/intake_metadata.py`: provide the deterministic unreviewed review payload.
- `app/ai_endpoints.py`: include review provenance in intake result and response.
- `app/config.py`: allow review provenance in the default strict result contract.
- `app/output_contracts.py`: seed a new default contract version for the new field.
- `app/main.py`: expose top-level review provenance in the response model.

## Tasks

1. Add failing tests for an unreviewed default payload, default contract support,
   and the next seeded default contract version.
2. Implement the default review payload and wire it into `cmms-intake` result and
   top-level API response.
3. Extend the default result contract and bump the seeded contract version so
   active strict contracts accept the new result property.
4. Run focused tests, the full unit suite, and compile checks for touched modules.
