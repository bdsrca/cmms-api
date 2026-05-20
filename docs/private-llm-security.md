# Private LLM Security

The project is designed around a company-private LLM route.

This can be a local model runtime, a private GPU endpoint, a secured internal model gateway, or a vendor-hosted private deployment. The important rule is that external clients do not call the model directly.

## Security goals

- Keep model endpoint secrets server-side.
- Keep raw API tokens out of logs.
- Hide internal model names from public UI.
- Redact sensitive work-request content by default.
- Prevent raw model output from becoming trusted CMMS data.
- Separate trial-token usage from admin operations.
- Apply quotas before expensive model calls.

## Request handling pattern

1. Caller submits text, transcript, or image-derived content.
2. Gateway validates token and scope.
3. Gateway checks request size and environment access.
4. Private LLM gateway builds a safe prompt from the approved template.
5. Model output is parsed as structured data.
6. Output contract runs.
7. CMMS environment validation runs.
8. Logger records safe metadata.
9. API returns a draft and warnings.

## Logging policy

Good public-safe log fields:

- timestamp;
- token prefix;
- environment code;
- endpoint;
- request category;
- result status;
- validation error count;
- model route label;
- latency;
- estimated token usage;
- safe hash of request body.

Fields to avoid in normal logs:

- full work-request text;
- private room or employee details;
- raw screenshots;
- audio files;
- model provider keys;
- full API tokens;
- private prompt templates;
- internal tenant IDs.

## Demo policy

The public showcase uses deterministic mock responses. It does not call a private model endpoint.
