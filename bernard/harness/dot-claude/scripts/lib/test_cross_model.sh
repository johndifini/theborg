#!/usr/bin/env bash
# Stub-model tests for cross-model-review.sh orchestration (no real models).
# Runners are single executable paths (the real-world contract), one per verdict.
set -uo pipefail
WIKI="/Users/lashawsalta/life-wiki"
SCRIPT="$WIKI/.claude/scripts/cross-model-review.sh"
fails=0
SB=$(mktemp -d)
trap 'rm -rf "$SB"' EXIT

mkstub() {  # $1=name $2=verdict-line(optional)
  cat > "$SB/$1" <<EOF
#!/usr/bin/env bash
cat >/dev/null
echo "Some reasoning about the claim."
${2:+echo "$2"}
EOF
  chmod +x "$SB/$1"
}
mkstub sup.sh   "VERDICT: SUPPORTED"
mkstub unsup.sh "VERDICT: UNSUPPORTED"
mkstub unc.sh   "VERDICT: UNCERTAIN"
mkstub none.sh  ""

INBOX="$SB/inbox.md"; LOG="$SB/cm.log"; STATE="$SB/state.tsv"
base=(env CM_INBOX="$INBOX" CM_ARCHIVE="$SB/archive.md" CM_LOG="$LOG" CM_TODAY=2026-06-14 CM_TIMEOUT=20 CM_STATE="$STATE")
ck() { if eval "$2"; then echo "PASS - $1"; else echo "FAIL - $1 :: $2"; fails=$((fails+1)); fi; }

# 1) AGREE
: > "$INBOX"
out=$("${base[@]}" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/sup.sh" bash "$SCRIPT" "claim one" --apply)
ck "agree: reports AGREE" '[[ "$out" == *"AGREE (SUPPORTED)"* ]]'
ck "agree: nothing filed" '! grep -q "cross-model" "$INBOX"'

# 2) DIVERGE filed
: > "$INBOX"
out=$("${base[@]}" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/unsup.sh" bash "$SCRIPT" "claim two" --apply)
ck "diverge: reports DIVERGE" '[[ "$out" == *"DIVERGE (A=SUPPORTED B=UNSUPPORTED)"* ]]'
ck "diverge: filed [cross-model]" 'grep -q "\[cross-model\]" "$INBOX"'
ck "diverge: names the claim" 'grep -q "claim two" "$INBOX"'

# 3) dedup
out=$("${base[@]}" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/unsup.sh" bash "$SCRIPT" "claim two" --apply)
ck "dedup: one line only" '[[ "$(grep -c "claim two" "$INBOX")" == "1" ]]'
ck "dedup: reports already in inbox" '[[ "$out" == *"already in inbox"* ]]'

# 4) UNCERTAIN -> diverge
: > "$INBOX"
out=$("${base[@]}" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/unc.sh" bash "$SCRIPT" "claim three" --apply)
ck "uncertain: DIVERGE" '[[ "$out" == *"DIVERGE (A=SUPPORTED B=UNCERTAIN)"* ]]'

# 5) missing verdict -> UNKNOWN -> diverge
: > "$INBOX"
out=$("${base[@]}" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/none.sh" bash "$SCRIPT" "claim four" --apply)
ck "no-verdict: UNKNOWN -> DIVERGE" '[[ "$out" == *"B=UNKNOWN"* ]]'

# 6) both UNSUPPORTED -> agree
: > "$INBOX"
out=$("${base[@]}" CM_MODEL_A="$SB/unsup.sh" CM_MODEL_B="$SB/unsup.sh" bash "$SCRIPT" "claim 4b" --apply)
ck "agree-unsupported: AGREE (UNSUPPORTED)" '[[ "$out" == *"AGREE (UNSUPPORTED)"* ]]'

# 7) dry-run files nothing
: > "$INBOX"
out=$("${base[@]}" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/unsup.sh" bash "$SCRIPT" "claim five")
ck "dry-run: detects DIVERGE" '[[ "$out" == *"DIVERGE"* ]]'
ck "dry-run: files nothing" '! grep -q "claim five" "$INBOX"'

# 8) no claim + empty register -> clean no-op
out=$("${base[@]}" CM_REGISTER="$SB/none.md" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/sup.sh" bash "$SCRIPT" --apply); rc=$?
ck "no-claim: exit 0" '[[ "$rc" == "0" ]]'
ck "no-claim: nothing to do" '[[ "$out" == *"nothing to do"* ]]'

# 9) claim auto-picked from a register
cat > "$SB/reg.md" <<EOF
# Working Hypotheses Register
## Hypotheses (1)
- **[[wikis/x]]** — autopicked claim text here
EOF
: > "$INBOX"
out=$("${base[@]}" CM_REGISTER="$SB/reg.md" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/unsup.sh" bash "$SCRIPT" --apply)
ck "auto-pick: uses register claim" 'grep -q "autopicked claim text here" "$INBOX"'

# 10) ROTATION: 2-hypothesis register, runs advance to a different claim each time
cat > "$SB/reg2.md" <<EOF
# Working Hypotheses Register
## Hypotheses (2)
- **[[wikis/a]]** — first hypothesis alpha
- **[[wikis/b]]** — second hypothesis beta
## Needs Verification (0)
EOF
: > "$STATE"
r1=$("${base[@]}" CM_REGISTER="$SB/reg2.md" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/sup.sh" bash "$SCRIPT" --apply >/dev/null 2>&1; grep -c . "$STATE")
claim1=$(grep -oE 'claim: .*' "$LOG" | tail -1)
ck "rotation: 1st run reviews alpha" '[[ "$claim1" == *"alpha"* ]]'
ck "rotation: state has 1 entry" '[[ "$r1" == "1" ]]'
"${base[@]}" CM_REGISTER="$SB/reg2.md" CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/sup.sh" bash "$SCRIPT" --apply >/dev/null 2>&1
claim2=$(grep -oE 'claim: .*' "$LOG" | tail -1)
ck "rotation: 2nd run advances to beta" '[[ "$claim2" == *"beta"* ]]'
ck "rotation: state now has 2 entries" '[[ "$(grep -c . "$STATE")" == "2" ]]'
# 3rd run: all reviewed -> picks least-recently-reviewed (alpha, dated earlier)
"${base[@]}" CM_REGISTER="$SB/reg2.md" CM_TODAY=2026-06-16 CM_MODEL_A="$SB/sup.sh" CM_MODEL_B="$SB/sup.sh" bash "$SCRIPT" --apply >/dev/null 2>&1
claim3=$(grep -oE 'claim: .*' "$LOG" | tail -1)
ck "rotation: 3rd run re-picks oldest (alpha)" '[[ "$claim3" == *"alpha"* ]]'
ck "rotation: state still 2 entries (no dupes)" '[[ "$(grep -c . "$STATE")" == "2" ]]'

echo
if [[ "$fails" -gt 0 ]]; then echo "$fails FAILED"; exit 1; fi
echo "ALL TESTS PASSED"
