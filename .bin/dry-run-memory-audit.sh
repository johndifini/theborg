#!/bin/bash
# Dry-run the monthly memory-governance audit without publishing anything.
#
# Migration step 6 of c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md: "Dry-run monthly
# and interactive modes; verify private data never enters the tracked snapshot,
# logs, or email." This script is the monthly (scheduled/headless) half. The
# interactive half is `/audit-assumptions` run in a session, which reports to the
# session and writes no state by its own overrides.
#
# The run is faithful where fidelity matters and redirected where publication
# would be irreversible:
#
#   real     BORG_ROOT is the live workspace, so discovery, coverage, validation,
#            the candidate snapshot, and the privacy scan all see real artifacts
#            and real private overlays. A dry run against a synthetic tree would
#            prove nothing about this workspace's private data.
#   sandbox  an OS-enforced Seatbelt policy makes the workspace read-only except
#            $BORG_ROOT/tmp (which STAGE 2 requires for workpapers) and this
#            run's output directory, so "scheduled runs make no changes" is
#            enforced rather than instructed. See the sandbox block below for
#            the two non-obvious precedence rules that shape it, and for the one
#            gap the before/after manifest exists to cover.
#   network  the allowlist holds api.anthropic.com only. smtp.gmail.com is
#            absent, so no email can leave the machine even if the redirect below
#            were ignored. It does not disable STAGE 7's research: WebSearch is
#            served through the model API rather than by the client, so the
#            assumptions still get live sources over the one allowed channel.
#   email    ${BORG_ROOT}/.bin/notify-email.sh is replaced by a capture stub that
#            writes the subject and body to files and exits 0.
#   state    STAGE 1 reads, and STAGE 10 writes, a state directory inside the
#            output directory instead of c4po/.claude/scheduled/state/.
#
# Usage:
#   dry-run-memory-audit.sh [--mode full|gate] [--cohort N] [--outdir DIR]
#                           [--model M] [--effort E] [--timeout SECONDS]
#
#   --mode full   (default) seed no state file, so STAGE 1 opens and the whole
#                 orchestrator runs.
#   --mode gate   seed a state file dated this month, so STAGE 1 must stop the
#                 run with no output, no email, and no state write. This is the
#                 cheap half of the dry run and it tests the once-per-month
#                 guard that `--mode full` has to bypass.
#   --mode probe  run neither the gate nor the audit: write four disposable
#                 files, two inside the writable roots and two outside them, and
#                 report which the sandbox actually blocked. This is the check
#                 that keeps the write-boundary claim honest, and it is cheap
#                 enough to run before every dry run.
#   --cohort N    cap STAGE 5's public semantic cohort at N audit units
#                 (default 2). Bounding the cohort bounds runtime; it does not
#                 touch any stage that decides what reaches the report.
#
# Verification is not part of this script's exit status: it runs the audit and
# captures artifacts. Scan them with .bin/tests/audit-privacy-scan.py and compare
# the recorded before/after tree manifests.

set -euo pipefail

MODE=full
COHORT=2
OUTDIR=""
MODEL=opus
EFFORT=high
TIMEOUT=3600

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)    MODE="$2"; shift 2 ;;
    --cohort)  COHORT="$2"; shift 2 ;;
    --outdir)  OUTDIR="$2"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    --effort)  EFFORT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

case "$MODE" in
  full|gate|probe) ;;
  *) echo "invalid --mode: '$MODE' (expected full, gate, or probe)" >&2; exit 64 ;;
esac

BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export BORG_ROOT

PROMPT_FILE="$BORG_ROOT/c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt"
[[ -f "$PROMPT_FILE" ]] || { echo "prompt not found: $PROMPT_FILE" >&2; exit 66; }

CLAUDE_BIN="${CLAUDE_BIN:-claude}"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || {
  echo "claude binary '$CLAUDE_BIN' not found on PATH" >&2; exit 127; }

if [[ -z "$OUTDIR" ]]; then
  OUTDIR="$(mktemp -d "${TMPDIR:-/tmp}/borg-audit-dryrun.$MODE.XXXXXX")"
fi
mkdir -p "$OUTDIR"/{bin,state,out}
OUTDIR="$(cd "$OUTDIR" && pwd)"

echo "dry run: mode=$MODE cohort=$COHORT outdir=$OUTDIR"

# ---------------------------------------------------------------- email capture
# Same argument shape as the real notify-email.sh (agent, optional subject, body
# on stdin) so the orchestrator's STAGE 9 call site needs no rewriting beyond the
# path. Exits 0 so STAGE 10 proceeds and the state-write path is exercised too.
cat > "$OUTDIR/bin/notify-email.sh" <<'STUB'
#!/bin/bash
set -euo pipefail
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/out"
printf '%s\n' "${1:-}" > "$OUT/email-agent.txt"
printf '%s\n' "${2:-}" > "$OUT/email-subject.txt"
cat > "$OUT/email-body.txt"
echo "captured $(wc -c < "$OUT/email-body.txt") bytes (dry run: nothing sent)" >&2
STUB
chmod +x "$OUTDIR/bin/notify-email.sh"

# ------------------------------------------------------------------ state seed
GATE_STATE="$OUTDIR/state/c4po-assumptions-audit-monthly.json"
if [[ "$MODE" == gate ]]; then
  printf '{"date": "%s", "flagged": 0}\n' "$(date +%Y-%m-01)" > "$GATE_STATE"
  echo "seeded current-month gate state: $GATE_STATE"
else
  rm -f "$GATE_STATE"
fi

# ------------------------------------------------------------------- manifests
# Recorded before and after so "the run changed nothing" is checkable rather than
# asserted. Covers tracked state, the private overlays, and the real state dir.
manifest() {
  {
    git -C "$BORG_ROOT" status --porcelain
    echo "--- overlays ---"
    find "$BORG_ROOT" -maxdepth 3 -path '*/.private/memory-inventory.yaml' \
      -exec shasum -a 256 {} \; 2>/dev/null | sort
    echo "--- state ---"
    find "$BORG_ROOT/c4po/.claude/scheduled/state" -type f \
      -exec shasum -a 256 {} \; 2>/dev/null | sort
    echo "--- prompt/command ---"
    shasum -a 256 "$PROMPT_FILE" \
      "$BORG_ROOT/c4po/.claude/commands/audit-assumptions.md" 2>/dev/null
  } 2>&1
}
manifest > "$OUTDIR/out/manifest-before.txt"

# ---------------------------------------------------------------------- sandbox
# Two properties of Claude Code's sandbox decide the shape of this policy, and
# both were established by probe on 2026-09-07 rather than assumed:
#
#   1. `allowWrite` ADDS to the writable set; it does not narrow it. The project
#      root is writable by default, so listing only $OUTDIR and tmp/ left the
#      entire workspace writable. A first version of this harness did exactly
#      that and claimed an enforced boundary it did not have.
#   2. `denyWrite` beats `allowWrite`, including for a subpath. So the blanket
#      form — deny $BORG_ROOT, allow $BORG_ROOT/tmp — does not work either: it
#      takes tmp/ away and STAGE 2 has nowhere to put its workpapers.
#
# What works is denying every top-level entry except tmp/. Deny is recursive, so
# one entry per top-level name covers every agent, cerebruh, repos, .git, the
# root instruction files, and the registry itself. One gap remains by
# construction: a brand-new top-level entry is not on the deny list and can
# still be created. The before/after manifest catches that, which is why the
# manifest — not the sandbox — is what this harness treats as proof.
DENY_JSON=$(python3 - "$BORG_ROOT" <<'PY'
import json, os, sys
root = sys.argv[1]
deny = [os.path.join(root, name) for name in sorted(os.listdir(root))
        if name != "tmp"]
print(json.dumps(deny))
PY
)

# Temp directories have to be writable too. `sync-codex-rule-skills.sh --check`
# pipes a rendered stub into `diff -q - FILE`, and diff spools stdin to a temp
# file; with temp denied it fails `Operation not permitted` on every comparison
# and the script reports all 25 bridges stale. The 2026-09-07 dry run did report
# exactly that, and a harness that manufactures a GENERATED_DRIFT finding is
# worse than no harness, because the finding is indistinguishable from a real
# one.
#
# Both temp roots are needed and neither is guessable from the other: the outer
# $TMPDIR is the per-user /var/folders path, while the CLI sets its own TMPDIR
# (/tmp/claude-<uid>) for the sandboxed run. Allowing /tmp and /private/tmp —
# the same directory either side of the macOS symlink — covers the second.
SETTINGS=$(python3 - "$OUTDIR" "$BORG_ROOT" "$DENY_JSON" "${TMPDIR:-/tmp}" <<'PY'
import json, os, sys
outdir, root, deny, tmpdir = (sys.argv[1], sys.argv[2], json.loads(sys.argv[3]),
                              sys.argv[4])
print(json.dumps({"sandbox": {
    "enabled": True,
    "failIfUnavailable": True,
    "autoAllowBashIfSandboxed": True,
    "allowUnsandboxedCommands": False,
    "network": {"allowedDomains": ["api.anthropic.com"],
                "allowManagedDomainsOnly": True},
    "filesystem": {"allowWrite": [outdir, os.path.join(root, "tmp"),
                                  tmpdir.rstrip("/"), "/tmp", "/private/tmp"],
                   "denyWrite": deny},
}}))
PY
)
python3 -c 'import json,sys; json.loads(sys.argv[1])' "$SETTINGS" || {
  echo "generated sandbox settings are not valid JSON" >&2; exit 65; }
printf '%s\n' "$SETTINGS" > "$OUTDIR/out/sandbox-settings.json"

# ------------------------------------------------------------------ probe mode
# The model reports its own exit statuses, but the verdict below is taken from
# the filesystem: a probe that trusted the report would be testing the model's
# honesty rather than the sandbox.
if [[ "$MODE" == probe ]]; then
  STAMP="probe-$$-$(date +%s)"
  ALLOWED=("$OUTDIR/$STAMP.txt" "$BORG_ROOT/tmp/$STAMP.txt")
  # The overlay target is resolved at run time rather than written down: this
  # script is tracked, and naming one owner's private directory in it would put
  # a concrete `<owner>/.private/` path into the public repository for no gain.
  OVERLAY_DIR="$(find "$BORG_ROOT" -maxdepth 2 -type d -name .private 2>/dev/null | head -1)"
  DENIED=("$BORG_ROOT/c4po/.claude/scheduled/state/$STAMP.json"
          "$BORG_ROOT/c4po/$STAMP.txt")
  [[ -n "$OVERLAY_DIR" ]] && DENIED+=("$OVERLAY_DIR/$STAMP.txt")

  PROBE="Sandbox write-boundary probe. Every target below is a new, disposable \
file that does not exist; nothing existing is read or modified. Run all of these \
commands, continue past any failure, and do not clean up afterwards."
  i=0
  for target in "${ALLOWED[@]}" "${DENIED[@]}"; do
    i=$((i + 1))
    PROBE+="
$i. printf p > $target ; echo \"probe$i=\$?\""
  done
  PROBE+="

Report each probe number and its exit status, then stop."

  cd "$BORG_ROOT/c4po"
  "$CLAUDE_BIN" -p "$PROBE" --model sonnet \
    --strict-mcp-config --no-session-persistence \
    --settings "$SETTINGS" --permission-mode acceptEdits \
    --add-dir "$OUTDIR" < /dev/null > "$OUTDIR/out/probe.log" 2>&1 || true

  PROBE_STATUS=0
  echo
  echo "write-boundary probe (verdict read from the filesystem, not the report):"
  for target in "${ALLOWED[@]}"; do
    if [[ -e "$target" ]]; then
      echo "  PASS  writable as intended: $target"
      rm -f "$target"
    else
      echo "  FAIL  should be writable but was blocked: $target"
      PROBE_STATUS=1
    fi
  done
  for target in "${DENIED[@]}"; do
    if [[ -e "$target" ]]; then
      echo "  FAIL  SHOULD BE BLOCKED but was written: $target"
      rm -f "$target"
      PROBE_STATUS=1
    else
      echo "  PASS  blocked as intended: $target"
    fi
  done
  echo
  echo "Known gap: a new top-level entry directly under $BORG_ROOT is not on the"
  echo "deny list and can still be created. The before/after manifest covers it."
  echo "probe verdict: $([[ $PROBE_STATUS -eq 0 ]] && echo PASS || echo FAIL)"
  exit $PROBE_STATUS
fi

# ----------------------------------------------------------------------- prompt
# The scheduled preamble is reproduced from run-scheduled-task.sh: without it the
# headless run matches the task name to /audit-assumptions and silently applies
# the interactive overrides, which would void exactly the path under test.
PROMPT_CONTENT=$(<"$PROMPT_FILE")
PROMPT_CONTENT=${PROMPT_CONTENT//\$\{BORG_ROOT\}/$BORG_ROOT}

read -r -d '' OVERRIDES <<EOF || true
--- END TASK INSTRUCTIONS ---

DRY-RUN SUBSTITUTIONS. This is a migration-step-6 acceptance run. The
instructions above are authoritative except for the redirections below, which
replace the corresponding instruction wherever it appears. Follow every other
stage exactly, including the STAGE 9 pre-delivery privacy scan and the STAGE 10
snapshot privacy scan — those checks are the subject of this test.

1. STAGE 1 reads its state file from $OUTDIR/state/c4po-assumptions-audit-monthly.json,
   not from the path in the instructions. Apply the gate rule to that file
   normally: if it exists and its date falls in the current calendar month, stop
   and output nothing.
2. STAGE 9 pipes the report into $OUTDIR/bin/notify-email.sh instead of
   \${BORG_ROOT}/.bin/notify-email.sh. Keep the same agent argument and subject
   format. The real sender is unreachable from this run.
3. STAGE 10 writes both files into $OUTDIR/state/ instead of
   \${BORG_ROOT}/c4po/.claude/scheduled/state/ — the snapshot as
   $OUTDIR/state/memory-inventory.json and the gate state as
   $OUTDIR/state/c4po-assumptions-audit-monthly.json. Write real files; the
   snapshot is scanned after this run and an in-memory snapshot proves nothing.
   Perform the pre-replacement privacy scan first, exactly as instructed.
4. STAGE 5 selects at most $COHORT public semantic audit units instead of 12.
   Use the same priority order and report the deferred count honestly.
5. The workspace is mounted read-only apart from $OUTDIR and
   \${BORG_ROOT}/tmp. A write elsewhere will fail; that is the report-only
   invariant being enforced rather than trusted. Do not try to work around it,
   and do not run bootstrap, --apply, or --show-private.
6. Direct network access is limited to the model API, so a client-side fetch of
   an arbitrary host will fail. WebSearch is served through that same API and
   still works, so do research normally and reach for UNVERIFIABLE only when a
   source genuinely cannot be checked — not merely because this is a dry run.
7. Write a short stage-by-stage trace to $OUTDIR/out/trace.txt as you go: one
   line per stage with its outcome and any finding counts. It must contain no
   private id, path, or content.

Finish by printing a one-paragraph summary of what was produced and where.
EOF

FULL_PROMPT="You are a scheduled (headless) run of the task named \
'c4po-assumptions-audit-monthly'. Execute the instructions below directly and in
full.

Do NOT invoke any skill or slash command that wraps this same task — in
particular the interactive companion whose name matches
'c4po-assumptions-audit-monthly'. That companion exists only for interactive use
and its overrides (skip the state gate, skip writing state, report to the session
instead of emailing) are WRONG here and would silently void this run. Perform
every phase below yourself, including the state gate, the report delivery, and
the state write, subject only to the DRY-RUN SUBSTITUTIONS at the end.

--- BEGIN TASK INSTRUCTIONS ---
$PROMPT_CONTENT

$OVERRIDES"

printf '%s' "$FULL_PROMPT" > "$OUTDIR/out/prompt-as-sent.txt"

# -------------------------------------------------------------------------- run
cd "$BORG_ROOT/c4po"
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "===== $START start dry run (mode=$MODE) =====" > "$OUTDIR/out/run.log"

# macOS ships no `timeout`, so the watchdog is a background sleep that signals
# the run. Killing the watchdog afterwards keeps it from outliving the script.
STATUS=0
"$CLAUDE_BIN" -p "$FULL_PROMPT" \
  --model "$MODEL" --effort "$EFFORT" \
  --strict-mcp-config --no-session-persistence \
  --settings "$SETTINGS" --permission-mode acceptEdits \
  --add-dir "$OUTDIR" \
  < /dev/null >> "$OUTDIR/out/run.log" 2>&1 &
RUN_PID=$!
( sleep "$TIMEOUT"; kill -TERM "$RUN_PID" 2>/dev/null ) &
WATCH_PID=$!
wait "$RUN_PID" || STATUS=$?
kill "$WATCH_PID" 2>/dev/null || true
wait "$WATCH_PID" 2>/dev/null || true

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) end dry run (exit $STATUS) =====" \
  >> "$OUTDIR/out/run.log"

manifest > "$OUTDIR/out/manifest-after.txt"

echo
echo "exit status: $STATUS"
echo "artifacts:"
ls -la "$OUTDIR/out" "$OUTDIR/state"
echo
if diff -u "$OUTDIR/out/manifest-before.txt" "$OUTDIR/out/manifest-after.txt" \
     > "$OUTDIR/out/manifest-diff.txt"; then
  echo "workspace manifest: UNCHANGED"
else
  echo "workspace manifest: CHANGED — see $OUTDIR/out/manifest-diff.txt"
fi
echo
echo "next: python3 $BORG_ROOT/.bin/tests/audit-privacy-scan.py --profile email \\"
echo "        $OUTDIR/out/email-body.txt $OUTDIR/out/email-subject.txt"
echo "      python3 $BORG_ROOT/.bin/tests/audit-privacy-scan.py --profile snapshot \\"
echo "        $OUTDIR/state/memory-inventory.json"
echo "      python3 $BORG_ROOT/.bin/tests/audit-privacy-scan.py --profile log \\"
echo "        $OUTDIR/out/run.log $OUTDIR/out/trace.txt"

exit $STATUS
