#!/usr/bin/env bash
# cross-model-review.sh — recommendation ④: cross-model adversarial reconciliation.
#
# Runs the SAME high-stakes claim through two independent models (Claude + Codex/
# gpt-5.5), each forced to end with a deterministic VERDICT token. Divergence is
# decided by comparing tokens — NOT by trusting either model — so a disagreement
# (or any UNCERTAIN) becomes a [cross-model] inbox item for the curator. Agreement
# is logged as a confidence signal. Diversity catches what one model rationalizes
# away. Heavy (two model runs) — intended for weekly cadence or manual use.
#
# Claim source: $1 if given, else the first hypothesis in the working-hypotheses
# register. Both model runners are env-injectable (CM_MODEL_A / CM_MODEL_B) so the
# orchestration is unit-testable with stubs.
#
# Egress: DEFAULT pair is Anthropic-only (Claude steelman vs skeptic) — sanctioned.
# The optional Codex runner sends wiki-derived PHI to OpenAI; that is cross-vendor
# egress and a curator decision, gated by the auto-classifier + a Bash permission rule.
#
# Usage: bash cross-model-review.sh ["claim text"] [--apply]
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
# Newest-first run logging via lib/wikilog.sh — unless a test/caller overrides
# CM_LOG, in which case log straight to that file (append) so stubs stay simple.
if [[ -n "${CM_LOG:-}" ]]; then
  LOG="$CM_LOG"
else
  source "$WIKI/.claude/scripts/lib/wikilog.sh"
  wikilog_open "cross-model-review"
  LOG="$WIKILOG_BUF"
  trap 'wikilog_flush' EXIT
fi
INBOX="${CM_INBOX:-$WIKI/.claude/inbox/wiki-question-inbox.md}"
ARCHIVE="${CM_ARCHIVE:-$WIKI/.claude/inbox/inbox-archive.md}"
REGISTER="${CM_REGISTER:-$WIKI/wikis/health/wiki/working-hypotheses.md}"
# DEFAULT = two independently-prompted Claude passes (steelman vs skeptic), which
# keeps egress Anthropic-only (sanctioned). To use a true cross-VENDOR second
# opinion, set CM_MODEL_B to cm-run-codex.sh — but that sends wiki PHI to OpenAI,
# a curator egress decision (the auto-classifier blocks it without an explicit
# Bash permission rule). See the egress note below.
CM_MODEL_A="${CM_MODEL_A:-$WIKI/.claude/scripts/lib/cm-run-claude.sh}"
CM_MODEL_B="${CM_MODEL_B:-$WIKI/.claude/scripts/lib/cm-run-claude-skeptic.sh}"
CM_TIMEOUT="${CM_TIMEOUT:-600}"
TODAY="${CM_TODAY:-$(date '+%Y-%m-%d')}"
mkdir -p "$(dirname "$LOG")"

APPLY=0; CLAIM=""
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    *) CLAIM="$a" ;;
  esac
done

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# Rotation state: which claims we've already reviewed and when. Lets weekly runs
# keep building on STATIC content — each run takes an unreviewed hypothesis, and
# once all are covered, re-examines the least-recently-reviewed one (by then it may
# have new supporting evidence). hash<TAB>date<TAB>decision.
STATE="${CM_STATE:-$WIKI/.claude/logs/cross-model-reviewed.tsv}"
touch "$STATE" 2>/dev/null || true
hash_of() { printf '%s' "$1" | cksum | cut -d' ' -f1; }

# Pick a claim from the register if none supplied: first unreviewed, else oldest.
if [[ -z "$CLAIM" && -f "$REGISTER" ]]; then
  best=""; best_date="9999-99-99"
  while IFS= read -r c; do
    [[ -z "$c" ]] && continue
    line=$(grep -E "^$(hash_of "$c")[[:space:]]" "$STATE" 2>/dev/null | tail -1)
    if [[ -z "$line" ]]; then CLAIM="$c"; break; fi
    d=$(printf '%s' "$line" | cut -f2)
    if [[ "$d" < "$best_date" ]]; then best_date="$d"; best="$c"; fi
  done < <(awk '/^## Hypotheses/{h=1;next} /^## /{if(h)h=0} h&&/^- /{sub(/^- \*\*\[\[[^]]*\]\] — /,"");print}' "$REGISTER")
  [[ -z "$CLAIM" ]] && CLAIM="$best"
fi
if [[ -z "$CLAIM" ]]; then
  echo "cross-model-review: no claim supplied and none in register — nothing to do."
  exit 0
fi

run_model() {  # $1=runner ; prompt on stdin ; echoes output. Hard timeout via
  # perl alarm+exec (no lingering watchdog processes; SIGALRM terminates on hang).
  local runner="$1"
  printf '%s' "$PROMPT" | perl -e 'alarm shift @ARGV; exec @ARGV or exit 127' \
    "$CM_TIMEOUT" "$runner" 2>&1
}

verdict_of() {  # last VERDICT token in the text, or UNKNOWN
  printf '%s' "$1" | grep -oiE 'VERDICT:[[:space:]]*(SUPPORTED|UNSUPPORTED|UNCERTAIN)' \
    | tail -1 | grep -oiE '(SUPPORTED|UNSUPPORTED|UNCERTAIN)' | tr '[:lower:]' '[:upper:]' \
    || echo "UNKNOWN"
}

PROMPT="You are independently reviewing one inference drawn from a private personal \
health wiki you can read in this repository (under wikis/). \
CLAIM: \"$CLAIM\". \
Using ONLY what the wiki actually contains, judge whether the claim is well-supported. \
State the single strongest counter-argument or gap. Do NOT recommend medications, \
doses, or diagnoses. Finish with EXACTLY one final line: \
'VERDICT: SUPPORTED' or 'VERDICT: UNSUPPORTED' or 'VERDICT: UNCERTAIN'."

log "=== cross-model review start :: claim: $CLAIM"
OUT_A=$(run_model "$CM_MODEL_A"); VA=$(verdict_of "$OUT_A")
OUT_B=$(run_model "$CM_MODEL_B"); VB=$(verdict_of "$OUT_B")
log "model A verdict: $VA"
log "model B verdict: $VB"
{
  echo "----- $TODAY claim: $CLAIM"
  echo "--- MODEL A ($CM_MODEL_A) verdict=$VA ---"; printf '%s\n' "$OUT_A"
  echo "--- MODEL B ($CM_MODEL_B) verdict=$VB ---"; printf '%s\n' "$OUT_B"
} >> "$LOG"

# UNKNOWN means the model run itself failed (API unreachable, timeout, no
# verdict token) — that is an ERROR, not a divergence. Do not file an inbox
# item and do not record rotation state, so the same claim retries next run.
# (2026-06-29: a ConnectionRefused outage filed UNKNOWN=UNKNOWN as a
# [cross-model] "divergence" — an API error dressed up as a clinical question.)
if [[ "$VA" == "UNKNOWN" || "$VB" == "UNKNOWN" ]]; then
  log "ERROR: model run failed (A=$VA B=$VB) — no divergence filed, state not recorded; will retry next run"
  log "=== cross-model review end ==="
  echo "cross-model-review: ERROR — model run failed (A=$VA B=$VB); see log"
  exit 1
fi

# Deterministic decision: agreement requires identical, decisive (non-UNCERTAIN,
# non-UNKNOWN) verdicts. Anything else is a divergence worth a human look.
if [[ "$VA" == "$VB" && "$VA" == "SUPPORTED" ]] || [[ "$VA" == "$VB" && "$VA" == "UNSUPPORTED" ]]; then
  DECISION="AGREE ($VA)"
else
  DECISION="DIVERGE (A=$VA B=$VB)"
fi
log "decision: $DECISION"

# Record rotation state so the next run advances to a different hypothesis.
if [[ "$APPLY" -eq 1 ]]; then
  h=$(hash_of "$CLAIM"); tmp=$(mktemp)
  grep -vE "^${h}[[:space:]]" "$STATE" 2>/dev/null > "$tmp" || true
  printf '%s\t%s\t%s\n' "$h" "$TODAY" "$DECISION" >> "$tmp"
  mv "$tmp" "$STATE"
fi

if [[ "$DECISION" == DIVERGE* ]]; then
  LINE="- $TODAY — Cross-model divergence: is this claim sound? \"$CLAIM\" — Claude=$VA, Codex=$VB; full reasoning in cross-model-review.log [cross-model]"
  qkey=$(printf '%s' "$LINE" | awk -F' — ' '{print $2}' | sed 's/[[:space:]]*$//')
  already=0
  for f in "$INBOX" "$ARCHIVE"; do
    [[ -f "$f" ]] && awk -F' — ' '/^- /{print $2}' "$f" | sed 's/[[:space:]]*$//' | grep -qxF "$qkey" && already=1
  done
  if [[ "$APPLY" -eq 1 && "$already" -eq 0 ]]; then
    [[ -f "$INBOX" ]] || printf '# Wiki Question Inbox\n\n' > "$INBOX"
    printf '%s\n' "$LINE" >> "$INBOX"
    log "filed [cross-model] divergence to inbox"
    echo "cross-model-review: DIVERGE (A=$VA B=$VB) — filed to inbox"
  else
    echo "cross-model-review: DIVERGE (A=$VA B=$VB)$([[ $already -eq 1 ]] && echo ' (already in inbox)')"
  fi
else
  echo "cross-model-review: AGREE ($VA) — logged as a confidence signal"
fi
log "=== cross-model review end ==="
