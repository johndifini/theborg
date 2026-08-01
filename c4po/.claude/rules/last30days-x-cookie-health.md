---
description: Diagnose and repair last30days X browser-cookie failures
---
# Keep last30days X authentication browser-backed

When X returns zero results or authentication errors and `~/.config/last30days/.env` has `FROM_BROWSER=firefox`, do not write `AUTH_TOKEN` or `CT0` or replace the backend merely because `--diagnose` shows `bird_authenticated: false` / `x_backend: null`; that command skips browser extraction. Verify the `auth_token` and `ct0` cookies and their expiry in the default Firefox profile's `cookies.sqlite`, then confirm with a live last30days query and its per-source footer. Repair by asking the user to log back into X in that Firefox profile. Scheduled jobs cannot self-heal and must report X as degraded, not as a quiet week.
