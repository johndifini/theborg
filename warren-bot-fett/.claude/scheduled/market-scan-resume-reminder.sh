#!/bin/bash
# One-shot reminder: the daily market scan was paused on 2026-08-06 for a ~4-month
# rebalance. This fires once (~2026-12-06 09:00), emails John, then removes itself.
# It does NOT re-enable the scan — resume is deliberately manual per John's choice.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BORG_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LABEL="com.theborg.warren-bot-fett-market-scan-resume-reminder"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_N="$(id -u)"

"$BORG_ROOT/.bin/notify-email.sh" warren-bot-fett "[Borg/warren-bot-fett] Market scan pause is up — re-enable?" <<'MD'
The daily **market scan** was paused on 2026-08-06 for your ~4-month account
rebalance. That window is up. It is still **disabled** — I did not auto-resume it.

To turn it back on:

```
launchctl enable gui/$(id -u)/com.theborg.warren-bot-fett-daily-market-scan
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.theborg.warren-bot-fett-daily-market-scan.plist
```

Or just ask me to resume the market scan.
MD

# Self-clean: unload and delete this one-shot so it never fires again.
launchctl bootout "gui/$UID_N/$LABEL" 2>/dev/null || true
rm -f "$PLIST" "$0"
