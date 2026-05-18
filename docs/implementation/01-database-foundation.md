# 01 - Database Foundation

The portal uses a local SQLite database at `data/portal.db`.

SQLite stores only portal configuration and telemetry:

- Users and sessions
- Generated API key metadata and hashes
- Environments and code lists
- API usage events
- Simple settings

It is not a CMMS database and does not store or create work orders.

The schema is initialized on FastAPI startup from `main.py`. Runtime database files are ignored by git through `.gitignore`.
