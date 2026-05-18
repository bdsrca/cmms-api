# 07 - Logs Reports KB

Process logs continue to write to:

```text
logs/cmms-llm-api.log
```

API usage events are also stored in SQLite for reporting.

Reports summarize usage by:

- Endpoint
- Status code
- API key name
- Environment code
- Call count
- Average duration

The Knowledge Base page and `/api/kb/status` endpoint are placeholders for future sources, indexes, and retrieval testing.
