# Portfolio Notes

## One-line summary

Secure CMMS private LLM API control plane with free-token onboarding, environment validation, draft-only AI intake, and a roadmap for voice, screenshot, multi-agent, and targeted analytics workflows.

## What to highlight in an interview

- The project does not trust raw model output.
- Free tokens are scoped and quota-controlled.
- Private LLM routing keeps provider secrets and model details server-side.
- Environment code lists make the AI useful for real CMMS setups.
- Voice and screenshot intake reuse the same validation pipeline.
- Multi-agent design is planned only where separate checks add value.
- The strongest boundary is review-before-write.

## Good portfolio paragraph

Built a secure API control plane for Megamation-style CMMS AI intake. The system lets users test a private company LLM with free scoped tokens, validates model output against schema contracts and environment-specific CMMS code lists, and returns reviewable work-order drafts instead of writing directly to the live CMMS. The roadmap extends the same control layer to voice intake, screenshot upload, multi-agent review, and targeted maintenance analytics.
