# Megamation CMMS SAGE API Showcase

## Secure private LLM control plane for future CMMS/EAM intake

### Executive summary

Maintenance teams do not need another chatbot that gives confident but unchecked suggestions. They need a controlled API layer that can take messy requests, extract useful structure, validate the result against the real CMMS environment, and keep the final action under human or policy control.

This project presents a practical architecture for a Megamation-style CMMS AI API. It highlights four ideas:

1. **Free-token onboarding** for safe pilots and demos.
2. **Company-private LLM routing** so model access is controlled by the organization, not by browser code.
3. **Deterministic validation** around non-deterministic model output.
4. **Future multi-agent expansion** for voice intake, screenshot intake, and targeted maintenance analytics.

The design is intentionally conservative. It does not let the model create live work orders by itself. It returns a validated draft and a review package. That boundary is what makes the system credible in an enterprise CMMS/EAM setting.

---

## 1. The problem

CMMS work requests often arrive in messy language:

- “The fan in the east corridor is screaming again.”
- “Room 205 is too hot after lunch.”
- “The pump fault screen says overload.”
- “The ceiling is leaking near the elevator.”

A CMMS, however, usually wants controlled values:

- Site
- Building
- Room
- Asset
- Trade
- Priority
- Work type
- Issue-to group
- Assign-to group
- Job type
- Cost center or department

A language model can help extract these fields, but raw extraction is not enough. Every client or site may use different codes. A value that looks reasonable to the model may be invalid in the selected environment. A secure API layer must do more than call the model.

It must answer four questions:

- Is the caller allowed to use this endpoint?
- Is the model output shaped correctly?
- Are the extracted values valid for this environment?
- Should this become a draft, a warning, or a blocked request?

---

## 2. Design principle

> The model can suggest. The API must validate. The CMMS write must remain controlled.

This principle shapes every part of the project.

The API can help a user move faster, but it does not replace CMMS policy. It should be able to say:

- “This looks like HVAC, but the asset match is weak.”
- “This priority is not configured in the selected environment.”
- “This token can test intake but cannot write to CMMS.”
- “This screenshot produced a draft, but a human must confirm location and asset.”

That is the difference between a demo and an operating layer.

---

## 3. System shape

The control plane has five layers:

1. **Access layer**: free tokens, API keys, scopes, quotas, expiry, revocation.
2. **Intake layer**: text, voice transcript, screenshot-derived text, helpdesk content.
3. **Private LLM layer**: company-controlled model route behind the API.
4. **Validation layer**: output contract plus environment-specific CMMS rules.
5. **Review layer**: draft result, warnings, normalized fields, audit metadata, future write gate.

The system is useful even before write-back exists. A team can test whether the AI understands their real maintenance language, whether their code lists have enough aliases, and which requests are ambiguous.

---

## 4. Free token model

A free token is a controlled entry point for pilots.

It should be treated as a product feature, not as a shortcut. A safe free token has:

- A visible prefix for support.
- A hashed secret in storage.
- Expiry date.
- Environment restriction.
- Endpoint scopes.
- Daily and monthly quota.
- Draft-only permission by default.
- Audit records for calls, denials, quota hits, and revocation.

Free tokens are especially useful when showing the private LLM API to a new customer. They allow real testing without exposing admin credentials and without turning on live write-back.

---

## 5. Private LLM model route

The project is designed for a company-private LLM route. That route could be local, hosted in a private cloud, served through a gateway, or connected to an enterprise model provider deployment. The browser does not need to know the model name or provider secret.

The private LLM boundary protects three things:

- **Data**: private work-request text should not be sprayed across uncontrolled tools.
- **Cost**: usage should pass through tenant, token, and quota checks.
- **Quality**: prompts, contracts, and model routes should be versioned and tested.

In a CMMS setting, this matters because maintenance language often contains buildings, staff names, room numbers, equipment names, safety incidents, and operational context.

---

## 6. Validation contracts

The API uses two validation stages.

### Output contract

The output contract checks the shape of the model response:

- Required fields exist.
- Field types are correct.
- Unexpected fields are blocked or ignored.
- Contract version is tracked.
- The response can be safely passed to business validation.

### Environment validation

Environment validation checks the extracted values against the selected CMMS environment:

- Building code exists.
- Room belongs to the building when the data is available.
- Priority is configured.
- Trade or work type is valid.
- Aliases are normalized.
- Unknown values become warnings or errors depending on policy.

This separation keeps the system understandable. Schema validity and CMMS validity are different problems.

---

## 7. Future voice and screenshot intake

Voice and screenshot intake should not be separate products. They are just new front doors into the same pipeline.

For voice:

1. User speaks.
2. Speech becomes transcript.
3. Transcript is editable.
4. API extracts a draft.
5. Validation returns warnings and normalized fields.
6. User reviews before action.

For screenshots or photos:

1. User uploads a screenshot or equipment photo.
2. Vision/OCR extracts visible text and context hints.
3. Intake agent builds a draft request.
4. Asset and location agents check possible matches.
5. Policy agent decides whether the result is safe to propose.
6. User reviews before CMMS write-back.

The future feature is not “image to work order” in one uncontrolled jump. It is “image to validated draft with evidence.”

---

## 8. Multi-agent roadmap

A single model call is enough for the first version. Multi-agent design becomes useful when the platform starts handling more valuable decisions.

The proposed agents are narrow:

- Intake Agent: turns raw input into a clear issue summary.
- Location Agent: resolves site/building/room hints.
- Asset Agent: suggests likely assets.
- Priority Agent: evaluates urgency and safety cues.
- Policy Agent: checks automation boundaries.
- Parts Agent: suggests materials for planning.
- Scheduling Agent: suggests queue or trade.
- Analytics Agent: links the request to trends and past failures.

These agents should not all write to the CMMS. Most should produce evidence, warnings, or recommendations. The final API response should include a readable review package.

---

## 9. Targeted data intelligence

Once intake is governed, the API can support targeted analytics:

- repeated failures by asset and symptom;
- validation failures by code list;
- high-friction phrases customers use;
- locations with recurring comfort complaints;
- assets where the model often lacks confidence;
- differences between user-reported priority and final approved priority;
- API usage patterns by token, environment, endpoint, and feature.

This is where the private LLM API becomes a data product. It does not only answer requests. It improves CMMS data quality and operational understanding.

---

## 10. Security posture

The public-safe security posture is simple:

- No raw provider secrets in the browser.
- No plaintext token storage.
- No default live write-back.
- No private prompt logging by default.
- No model route shown in public UI.
- No production tenant names in public docs.
- No work-order creation without review or policy approval.
- No local process controls exposed through the demo UI.

The stronger production version would add formal secrets management, signed audit events, rate limits, request body size limits, file scanning for uploads, model allowlists, tenant-level budget enforcement, and SIEM-friendly logs.

---

## 11. What this proves

This project proves that AI for CMMS/EAM is not mainly about prompt writing. It is about engineering the layer between natural language and operational systems.

That layer needs product judgment:

- Let people test with free tokens.
- Keep the company model private.
- Validate against each environment.
- Return drafts, not unchecked writes.
- Design for voice and screenshots without weakening security.
- Use multi-agent design where separate checks add value.
- Turn usage and validation data into better maintenance analytics.

The result is a credible path from local AI demo to future CMMS/EAM assistant.
