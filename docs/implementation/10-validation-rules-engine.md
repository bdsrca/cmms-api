# 10 - Validation Rules Engine

Validation Rules connect Environment Code Lists to AI output validation.

Implemented v1 fields:

- building
- room
- priority
- work_order_type
- assign_to
- issue_to
- job_type

Each rule supports:

- enabled
- required
- must_match_code_list
- allow_unknown
- severity: `error` or `warning`
- code category mapping

Validation is post-processing only. It does not change the model prompt.

Main helper:

```python
validate_ai_output(environment_code: str, payload: dict) -> dict
```

The helper returns:

- `valid`
- `errors`
- `warnings`
- `normalized`

Matching checks enabled code values by:

- code
- description/label
- aliases

`/api/ai/cmms-intake` now includes an `ai_validation` block when `environment_code` is supplied.
