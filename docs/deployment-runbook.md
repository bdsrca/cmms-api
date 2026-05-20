# Deployment Runbook

This showcase does not include production secrets or real endpoints. A production deployment should use a stronger runbook.

## Minimum deployment checklist

- Store secrets outside the repository.
- Use HTTPS only.
- Hash API tokens before storage.
- Show raw token value only once.
- Configure request size limits.
- Configure upload file type limits.
- Verify environment access on every request.
- Apply rate limits before model calls.
- Keep model provider secrets server-side.
- Redact logs.
- Add backup and restore for configuration database.
- Add operational alerts for failed model route, quota spikes, and validation failures.

## Demo deployment

A demo deployment can use:

- a local FastAPI service;
- a local or private LLM route;
- a Cloudflare tunnel for temporary access;
- a demo environment with fake code lists;
- free tokens with small quotas.

Temporary public access should be closed after the demo.
