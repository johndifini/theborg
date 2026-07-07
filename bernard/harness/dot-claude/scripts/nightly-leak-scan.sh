#!/usr/bin/env bash
# nightly-leak-scan.sh — deep leak scan of the whole wiki using the sanitizer's
# 5-tier scanner (scripts/scan-wiki-leaks.py) as the oracle.
#
# The scanner's DEFINITE tier has known, curator-triaged false positives
# (2026-06-11 triage: Luhn-passing date+timestamp filenames read as credit
# cards; Epic registry IDs shaped like SSNs; provider office phones kept by
# policy; PATIENT-001's own codename digits as "account"). Those live in a
# baseline file; the gate trips only on NEW or INCREASED findings per
# file+class — a real leak in an already-listed file raises its count and
# still trips.
#
# Usage:
#   nightly-leak-scan.sh                    scheduled / manual scan
#   nightly-leak-scan.sh --accept-baseline  after curator triage of new
#       findings: bless the most recent run's DEFINITE set as the new baseline
#
# Writes .claude/logs/leak-scan-status, consumed by vps-mirror-sync.sh
# (fail-closed gate) and harness-health.sh:
#     clean <ISO timestamp>      — no DEFINITE findings beyond the baseline
#     DEFINITE <ISO timestamp>   — new leak-class findings; mirror gates shut
#
# Scheduled by com.life-wiki.scan at 02:30 — deliberately BEFORE gbrain dream
# (03:15) and the mirror push (07:00), so a leak is caught before the wiki's
# only external surface updates. Scanner output is digit-masked (safe to log).
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
SAN="$HOME/Devops/life-wiki-sanitizer"
LOGDIR="$WIKI/.claude/logs"
STATUS="$LOGDIR/leak-scan-status"
BASELINE="$WIKI/.claude/reference/leak-scan-baseline.tsv"
CURRENT="$LOGDIR/leak-scan-current.tsv"
PY="$SAN/.venv/bin/python3"

mkdir -p "$LOGDIR"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "leak-scan"
trap 'wikilog_flush' EXIT
ts() { date '+%Y-%m-%dT%H:%M:%S'; }
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Wiki Leak Scan\" sound name \"Ping\"" 2>/dev/null || true; }

# scanner output -> "path<TAB>class<TAB>count" lines, sorted (paths/classes
# only — masked counts, never values)
normalize() {
  grep ': DEFINITE ' | sed 's/ *|.*//' | awk -F': DEFINITE ' '
    NF == 2 {
      n = split($2, a, ",")
      for (i = 1; i <= n; i++) {
        gsub(/^ +| +$/, "", a[i])
        if (split(a[i], kv, "×") == 2 && kv[1] != "")
          printf "%s\t%s\t%s\n", $1, kv[1], kv[2]
      }
    }' | sort
}

if [[ "${1:-}" == "--accept-baseline" ]]; then
  if [[ ! -s "$CURRENT" ]]; then
    echo "No $CURRENT from a prior run — run a scan first." >&2
    exit 1
  fi
  mkdir -p "$(dirname "$BASELINE")"
  {
    echo "# leak-scan-baseline.tsv — curator-triaged DEFINITE false positives."
    echo "# Gate trips only on findings NOT covered by these file+class counts."
    echo "# Original triage 2026-06-11 (see AGENT-HANDOFF.md): credit_card ="
    echo "# Luhn-passing timestamp filenames; ssn = Epic registry IDs; phone ="
    echo "# provider office numbers (kept by policy); account = PATIENT-001"
    echo "# codename digits. Re-bless after triage: nightly-leak-scan.sh --accept-baseline"
    echo "# Accepted: $(ts)"
    cat "$CURRENT"
  } > "$BASELINE"
  echo "Baseline accepted: $(grep -vc '^#' "$BASELINE") finding line(s) -> $BASELINE"
  exit 0
fi

{
  echo "=== leak scan started $(ts) ==="
  if [[ ! -x "$PY" || ! -f "$SAN/scripts/scan-wiki-leaks.py" ]]; then
    echo "ERROR: sanitizer venv or scanner missing — status left untouched (mirror gates shut on staleness)"
    exit 1
  fi
  cd "$SAN"
  set +e
  OUT=$("$PY" scripts/scan-wiki-leaks.py "$WIKI" 2>&1)
  RC=$?
  set -e
  printf '%s\n' "$OUT"
  printf '%s\n' "$OUT" | normalize > "$CURRENT"

  if [[ $RC -eq 0 ]]; then
    echo "clean $(ts)" > "$STATUS"
    echo "RESULT: clean (no DEFINITE findings at all)."
  elif [[ ! -s "$BASELINE" ]]; then
    echo "DEFINITE $(ts)" > "$STATUS"
    echo "RESULT: DEFINITE findings and no triaged baseline — mirror gated shut."
    echo "  After curator triage: bash .claude/scripts/nightly-leak-scan.sh --accept-baseline"
    notify "Leak scan: DEFINITE findings, no baseline — mirror gated shut"
  else
    DELTA=$(awk -F'\t' '
      NR == FNR { if ($0 !~ /^#/) base[$1 FS $2] = $3 + 0; next }
      { key = $1 FS $2; if (!(key in base) || $3 + 0 > base[key]) print }
    ' "$BASELINE" "$CURRENT")
    known=$(grep -vc '^#' "$BASELINE" || true)
    if [[ -z "$DELTA" ]]; then
      echo "clean $(ts)" > "$STATUS"
      echo "RESULT: clean — all DEFINITE findings covered by the triaged baseline (${known} known line(s))."
    else
      echo "DEFINITE $(ts)" > "$STATUS"
      echo "RESULT: NEW DEFINITE findings beyond the triaged baseline — mirror gated shut:"
      printf '%s\n' "$DELTA" | sed 's/^/  NEW: /'
      echo "  Triage each line; real leaks: re-run sanitizer pass. False positives:"
      echo "  bash .claude/scripts/nightly-leak-scan.sh --accept-baseline"
      notify "Leak scan: NEW DEFINITE findings — mirror gated shut. See leak-scan.log"
    fi
  fi
  echo "=== leak scan finished $(ts) ==="
} >> "$WIKILOG_BUF" 2>&1
