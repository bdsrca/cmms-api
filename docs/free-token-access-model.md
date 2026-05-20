# Free Token Access Model

Free token access is a controlled way to let users test the private CMMS AI API without giving them admin access.

A free token is useful for:

- sales demos;
- client pilots;
- internal champions;
- integration testing;
- training environments;
- limited proof-of-concept usage.

## What a free token can do

A safe default token can call draft-only endpoints:

- `intake:text`
- `intake:voice-transcript`
- `intake:screenshot-summary`
- `contracts:validate`
- `analytics:basic-summary`

It should not be allowed to:

- create live work orders;
- modify environment code lists;
- change validation rules;
- manage users;
- create other tokens;
- access private model settings;
- export full logs.

## Suggested token fields

| Field | Purpose |
| --- | --- |
| `token_id` | Internal ID used in logs. |
| `prefix` | Safe display prefix for support. |
| `secret_hash` | Hash of the token secret. The raw token is shown only once. |
| `environment_code` | Restricts usage to one environment or demo sandbox. |
| `scopes` | Explicit list of allowed actions. |
| `expires_at` | Automatic expiry. |
| `daily_quota` | Prevents open-ended use. |
| `monthly_quota` | Controls pilot cost. |
| `status` | Active, expired, revoked, or suspended. |
| `created_by` | Who issued the token. |

## Free does not mean unsafe

The word `free` only describes the commercial model. It should never mean unrestricted access.

The API should still check:

- signature or token hash;
- expiry;
- scope;
- environment;
- quota;
- request size;
- abuse patterns;
- audit policy.
