# Source Code Map

The source files are small public-safe examples. They are not a production server.

| File | Purpose |
| --- | --- |
| `free_token_policy.py` | Issues, verifies, consumes, and revokes scoped free tokens. |
| `secure_logger.py` | Writes redacted metadata-only events. |
| `contract_validator.py` | Validates output shape and types. |
| `environment_validator.py` | Normalizes draft fields against CMMS code lists. |
| `private_llm_gateway.py` | Mock private model route with deterministic output. |
| `agent_orchestrator.py` | Simple multi-agent review package builder. |
| `analytics_router.py` | Produces targeted analytics from safe event data. |
| `intake_pipeline.py` | Wires token, model, contract, environment, agents, and logging. |
| `demo.py` | Runs a sample intake request. |
| `tests/test_showcase.py` | Verifies token scope, validation, redaction, and pipeline behavior. |
