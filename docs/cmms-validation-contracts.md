# CMMS Validation Contracts

Language models are flexible. CMMS systems are structured. The validation layer is the bridge.

The project uses two stages.

## 1. Output contract validation

This stage checks the shape of the model response.

Example contract:

```json
{
  "required": ["summary", "priority", "trade", "location_hint"],
  "types": {
    "summary": "string",
    "priority": "string",
    "trade": "string",
    "location_hint": "string",
    "asset_hint": "string",
    "confidence": "number"
  },
  "allow_extra_fields": false
}
```

This stage answers:

- Did the model return JSON?
- Are required fields present?
- Are field types correct?
- Are there unexpected fields?

## 2. Environment validation

This stage checks whether the extracted values match the selected CMMS environment.

Examples:

- `HVAC` is a valid trade.
- `P1` is valid in one environment, but `URGENT` is valid in another.
- `ARC` may be a building alias for `ARTS_RESOURCE_CENTRE`.
- A room may require building context before it is trusted.

## Warnings vs errors

Warnings are useful when a draft can still be reviewed:

- weak asset match;
- location hint needs confirmation;
- multiple aliases matched;
- priority inferred from wording.

Errors should block promotion:

- missing required field;
- invalid environment;
- disabled code;
- token lacks scope;
- model response fails schema;
- unsupported upload type.
