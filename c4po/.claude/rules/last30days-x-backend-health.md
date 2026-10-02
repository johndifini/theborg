---
name: last30days-x-backend-health
description: "When last30days returns zero X results or X errors: X runs on XAI_API_KEY (macOS 27 blocks the Firefox cookie path for headless runs). Check the xAI credit balance first; do not revert to browser cookies."
---
# last30days X runs on xAI — an empty X means credit or key first

Since 2026-09-30, last30days reaches X through `XAI_API_KEY` in
`~/.config/last30days/.env` (chmod 600). The old Firefox cookie path cannot
work here: macOS 27 app-data protection blocks every Claude process tree from
`~/Library/Application Support/Firefox`. It fails with "Operation not
permitted" even with the Claude sandbox disabled, and it silently returned
zero X results for W38–W40. Do not suggest re-logging into Firefox, writing
`AUTH_TOKEN`/`CT0`, or removing the key.

When X is empty or erroring:

1. Check the prepaid credit at console.x.ai first. Auto top-up is off, and
   with a key present last30days also routes its planner and reranker to
   `grok-4-1-fast`, so all three draw on the same balance.
2. Confirm `XAI_API_KEY` is still set in `~/.config/last30days/.env`.
3. Confirm with a live query's per-source footer. `--diagnose` flags such as
   `bird_authenticated` describe the old cookie path and prove nothing here.

Scheduled jobs cannot top up credit themselves. They must report X as
degraded and name the likely cause, never treat it as a quiet week.
