---
name: headless-tcc-consent-hang
description: "When a headless scheduled job hangs with no output, or when pointing a job or tool cache at a folder: headless claude blocks forever on a macOS TCC consent dialog for ~/Documents, ~/Desktop or ~/Downloads. Read TCC's unified log to confirm."
---
# A hung headless job may be waiting on a TCC dialog

Headless claude has no Files and Folders grant. Its first touch of ~/Documents,
~/Desktop or ~/Downloads does not fail: macOS shows a consent dialog on the
Studio's screen and the call blocks forever, so `|| true` never runs. On
2026-09-29 the mrs-beast image job sat this way for 26 hours and ignored
SIGTERM. Never point a scheduled job or tool cache at those folders.

To diagnose a `claude -p` that is alive with no children, read TCC's log, not
TCC.db:

```sh
/usr/bin/log show --last 3d --style compact --predicate 'subsystem == "com.apple.TCC" AND eventMessage CONTAINS "AUTHREQ_PROMPTING"'
```

A prompt with no matching AUTHREQ_RESULT is the cause.
