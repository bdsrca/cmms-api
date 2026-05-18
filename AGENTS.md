# Local CMMS LLM API Agents

This project uses a deterministic workflow-based multi-agent design. It is not an autonomous agent system.

## Agent Design

1. Classifier Agent
   - Uses the local Ollama model `qwen3:8b`.
   - Classifies the request type only.
   - Returns structured JSON with `request_type` and `confidence`.

2. Field Extractor Agent
   - Uses the same local Ollama model `qwen3:8b`.
   - Extracts building, room, priority, and summary from the request text.
   - Returns structured JSON only.

3. Rule Validator
   - Deterministic Python code.
   - Validates request type, building, room, priority, missing fields, review requirements, and advisory state.
   - Gates every downstream action.

4. Draft Generator Agent
   - Uses the same local Ollama model `qwen3:8b`.
   - Generates draft work order description, internal note, and client reply.
   - Must not claim that a work order was created.

## Safety Boundaries

- No agent can write to CMMS directly.
- No agent can create work orders automatically.
- No agent can approve requests.
- No agent can send emails automatically.
- The API must not expose Ollama directly.
- The API must not add a generic `/chat` endpoint.
- First version is advisory and draft-only.
- All model output must be validated by deterministic server-side rules before use.

## Operator UI

- `/ui` is a local browser operator console.
- The UI is not an autonomous agent.
- The UI must call only the controlled advisory endpoints.
- Server-side validation remains authoritative.
- Cloudflare Tunnel must stay a manual operator action unless this policy is explicitly changed.
- Local process controls must require `x-api-key` and local client access.
- Logs must not record API keys or full secrets.
- Generated API keys must be stored hashed, never plaintext.
- API key management and process start/stop controls require an authenticated admin portal session.
- `LLM_API_KEY` and generated API keys can call AI endpoints only; they must not grant admin portal access.
