# 02 - Auth And Roles

The portal supports login/logout with HTTP-only session cookies.

Admin bootstrap uses:

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="use-a-long-unique-password"
```

The old `change-this-password` placeholder is rejected. Passwords are stored with Argon2 hashes. Existing legacy PBKDF2 hashes are accepted only for migration and are rehashed after successful login.

Session rules:

- Session tokens are random and only their hashes are stored.
- Session cookies are `HttpOnly`.
- Session cookies are `Secure` when the request is HTTPS or `X-Forwarded-Proto` includes `https`.
- Sessions expire and logout deletes the stored session.
- Login has a simple per-user/per-client failed-attempt limit.

The UI has two roles:

- `admin`: can manage users, API keys, environments, settings, and local system controls.
- `user`: can use the portal test tools, API builder, logs, reports, and KB placeholder pages.

Direct API calls still use `x-api-key`.

Admin endpoints verify role on the backend. Frontend menu hiding is only a convenience layer.
