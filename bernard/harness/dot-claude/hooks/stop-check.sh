#!/usr/bin/env bash
# Stop hook — one mechanical reminder per session when wiki content has
# uncommitted changes but AGENT-HANDOFF.md was never touched (coordination
# contract step 6). Targets the recorded failure mode where a parallel
# session ended with work uncommitted and unrecorded (2026-06-11).
#
# Blocks at most ONCE per session (marker file), and never re-blocks within
# the same stop event (stop_hook_active).
set -uo pipefail
WIKI="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WIKI" || exit 0

input=$(cat)
read -r session_id stop_active < <(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(d.get("session_id", "unknown") or "unknown", d.get("stop_hook_active", False))
' 2>/dev/null) || exit 0

[[ "${stop_active:-False}" == "True" ]] && exit 0

marker=".claude/tmp/stop-reminder-${session_id:-unknown}"
[[ -f "$marker" ]] && exit 0

# Anything dirty under wiki content?
dirty=$(git status --porcelain -- wikis ingest 2>/dev/null || true)
[[ -z "$dirty" ]] && exit 0

# Handoff also dirty (i.e. being updated this session)? Then we're fine.
handoff_dirty=$(git status --porcelain -- AGENT-HANDOFF.md 2>/dev/null || true)
[[ -n "$handoff_dirty" ]] && exit 0

mkdir -p .claude/tmp && touch "$marker"
echo "life-wiki coordination contract: wiki content has uncommitted changes but AGENT-HANDOFF.md is untouched. Before ending the session, update Last Session + ingest queue counts + lint result in AGENT-HANDOFF.md (see /session-wrap). If this stop is mid-task and intentional, just stop again — this reminder fires once per session." >&2
exit 2
