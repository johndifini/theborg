#!/usr/bin/env bash
# wiki-status.sh — one-shot "is everything running the way I want, and what did
# other agents change" dashboard. READ-ONLY: safe to run anytime, by any agent or
# the curator, even while other sessions are writing. Takes no lock, writes nothing.
#
#   bash .claude/scripts/wiki-status.sh
#
# Sections: watchdog verdict · scheduled-job health · mirror/leak gate · queues ·
# git state (what parallel sessions left) · live writers · structural lint.
set -uo pipefail
WIKI="/Users/lashawsalta/life-wiki"; cd "$WIKI" || exit 1
L="$WIKI/.claude/logs"
now=$(date +%s)
age_h() { [ -e "$1" ] && echo $(( (now - $(stat -f %m "$1")) / 3600 )) || echo "?"; }
hr() { printf '%s\n' "──────────────────────────────────────────────────────────"; }
# Capture launchctl list ONCE, then match in pure bash. Piping into `grep -q`
# under `set -o pipefail` races: grep closes the pipe on first match → launchctl
# gets SIGPIPE (141) → pipefail reports the pipeline as failed for whichever
# labels appear early in the output. Pattern-match on the captured string instead.
LCLIST="$(launchctl list 2>/dev/null || true)"
loaded() { case "$LCLIST" in *"$1"*) echo "loaded" ;; *) echo "NOT LOADED" ;; esac; }

printf '\nLIFE-WIKI STATUS — %s   (branch: %s)\n' "$(date '+%Y-%m-%d %H:%M')" "$(git branch --show-current 2>/dev/null)"
hr

# 1 — watchdog headline (the surface that also prints at session start)
echo "▶ WATCHDOG  (harness-health, daily 08:00 — the single source of 'needs you')"
if [ -f "$L/harness-status" ]; then
  state=$(awk -F'\t' 'NR==1{print $1}' "$L/harness-status")
  since=$(awk -F'\t' 'NR==1{print $3}' "$L/harness-status")
  case "$state" in
    green) echo "  ✅ all green" ;;
    fixed) echo "  🔧 auto-fixed something last run (see harness-health.log)" ;;
    needs-you) echo "  ⛔ NEEDS YOU (since $since):"; awk -F'\t' 'NR>1{print "       • "$0}' "$L/harness-status" ;;
    *) echo "  state: $state" ;;
  esac
  echo "     (last watchdog run: $(age_h "$L/harness-health.log")h ago)"
else echo "  (no harness-status yet — watchdog hasn't run)"; fi
hr

# 2 — scheduled jobs: installed in launchd? and did they run recently?
echo "▶ SCHEDULED JOBS    loaded?        last ran        expect"
# name | launchd label | freshness file (rel to logs) | max-age-hours
jobs=(
  "leak scan (02:30)|com.life-wiki.scan|leak-scan-status|26"
  "gbrain dream (03:15)|com.lashawsalta.gbrain-dream|gbrain-dream.log|26"
  "synthesis (06:00)|com.life-wiki.synthesis|daily-synthesis.log|26"
  "mirror sync (07:00)|com.lashawsalta.wiki-mirror-sync|wiki-mirror-sync.log|26"
  "harness-health (08:00)|com.lashawsalta.harness-health|harness-health.log|26"
  "daily ingest (12:00)|com.life-wiki.ingest|daily-ingest.log|26"
  "wiki eval (09:15)|com.life-wiki.eval|wiki-eval.log|36"
  "gbrain sync (daily 3am)|com.lashawsalta.gbrain-sync|gbrain-sync.log|26"
)
for row in "${jobs[@]}"; do
  IFS='|' read -r nm label f max <<< "$row"
  ld=$(loaded "$label")
  a=$(age_h "$L/$f")
  flag=""
  [ "$ld" = "NOT LOADED" ] && flag="  ⛔"
  if [ "$a" != "?" ] && [ "$a" -gt "$max" ] 2>/dev/null; then flag="${flag}  ⚠ stale"; fi
  printf "  %-22s %-13s  %sh ago%s\n" "$nm" "$ld" "$a" "$flag"
done
hr

# 3 — mirror / leak gate (controls whether health edits reach Bernard)
echo "▶ MIRROR → BERNARD"
if [ -f "$L/leak-scan-status" ]; then
  s=$(head -1 "$L/leak-scan-status"); ga=$(age_h "$L/leak-scan-status")
  if printf '%s' "$s" | grep -q '^clean' && [ "$ga" -lt 48 ] 2>/dev/null; then
    echo "  gate: ✅ OPEN  ($s)"
  else echo "  gate: ⛔ CLOSED — push refused  ($s, ${ga}h old)"; fi
else echo "  gate: ⛔ no leak-scan status"; fi
echo "  last successful push line:"
# newest-first log: first match above the migration divider is the newest;
# if none yet, fall back to the newest (=last) match in the append-era region.
awk 'mig==0 && /sync complete/ {print; found=1; exit}
     /format migration/ {mig=1}
     mig && /sync complete/ {last=$0}
     END {if (!found && last) print last; if (!found && !last) print "(none in log)"}' \
  "$L/wiki-mirror-sync.log" 2>/dev/null | sed 's/^/     /'
hr

# 4 — queues
echo "▶ QUEUES"
iq=$(find ingest -path ingest/audio -prune -o -name '*.md' ! -name '.gitkeep' -print 2>/dev/null | wc -l | tr -d ' ')
ib=$(grep -c '^- ' .claude/inbox/wiki-question-inbox.md 2>/dev/null); ib=${ib:-0}
bc=$(grep -c '^- ' .claude/inbox/bernard-conversation-log.md 2>/dev/null); bc=${bc:-0}
echo "  ingest pending:        $iq    (run /ingest)"
echo "  question inbox:        $ib    (run /inbox-triage)"
echo "  Bernard convo log:     $bc    (pulled exchanges awaiting bernard-learn)"
hr

# 5 — git state: what OTHER agents / the curator left in the shared tree
echo "▶ GIT STATE  (local-only repo — no remote; 'pick up changes' = read these)"
echo "  last 3 commits:"; git log --oneline -3 2>/dev/null | sed 's/^/     /'
dirty=$(git status --porcelain 2>/dev/null)
ndirty=$(printf '%s' "$dirty" | grep -c . || true)
echo "  uncommitted files: $ndirty  (in-flight work from any session — review before you commit)"
if [ "$ndirty" -gt 0 ]; then printf '%s\n' "$dirty" | head -20 | sed 's/^/     /'; [ "$ndirty" -gt 20 ] && echo "     … +$((ndirty-20)) more"; fi
echo "  handoff updated: $(sed -n 's/^updated: //p' AGENT-HANDOFF.md 2>/dev/null | head -1)  → read AGENT-HANDOFF.md for the in-flight story"
hr

# 6 — live writers RIGHT NOW (is it safe to start writing?)
echo "▶ LIVE WRITERS"
wl="$WIKI/.claude/tmp/wiki-write.lock"
if [ -d "$wl" ]; then
  echo "  ⚠ wiki-write lock HELD by: $(cat "$wl/holder" 2>/dev/null) (since $(cat "$wl/ts" 2>/dev/null)) — another writer is active; wait or coordinate"
else echo "  ✅ wiki-write lock free — safe to take it for write-heavy work"; fi
for p in daily-synthesis daily-ingest build-backlinks bernard-learn vps-mirror-sync; do
  pgrep -f "$p" >/dev/null 2>&1 && echo "  ⚙ running: $p"
done
hr

# 7 — structural lint (fast, deterministic)
echo "▶ STRUCTURAL LINT"
bash "$WIKI/.claude/scripts/wiki-lint-structural.sh" 2>/dev/null | grep '^Summary:' | sed 's/^/  /'
hr
echo "Tip: deeper checks → /lint (semantic) · gbrain orphans (graph) · bash .claude/scripts/wiki-eval.sh (golden set)"
echo
