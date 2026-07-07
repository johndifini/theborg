#!/usr/bin/env bash
# post-ingest-verify.sh — mandatory close-out check for BATCH / PARALLEL ingests.
#
# Why this exists: single-file ingests are reliable, but parallel multi-agent
# batches have twice re-introduced real PHI and left duplicate "-source.md"
# artifacts (see AGENT-HANDOFF.md). Lint does not catch either. Run this after
# any batch ingest, before close-out.
#
# It NEVER prints PHI values — only filenames and match counts, consistent with
# the .claude/tmp/phi-*.log convention.
#
# Exit 0 = clean. Exit 1 = findings that must be triaged before close-out.

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2

# bash 3.2 (macOS default) has no `mapfile`; read newline-delimited into an array.
# The `|| [[ -n ]]` clause captures a final line that lacks a trailing newline,
# exactly once.
read_lines() {  # usage: read_lines ARRAYNAME < input
  local __arr="$1"; local __line; eval "$__arr=()"
  while IFS= read -r __line || [[ -n "$__line" ]]; do
    eval "$__arr+=(\"\$__line\")"
  done
}
ROOT="$(pwd)"
TARGETS="$HOME/Devops/life-wiki-sanitizer/secrets/redaction_targets.json"
fail=0

echo "POST-INGEST VERIFY — $(date +%F)"
echo "================================================"

# ---- 1. PHI re-introduction sweep -------------------------------------------
echo
echo "[1/4] PHI re-introduction sweep"
if [[ ! -f "$TARGETS" ]]; then
  echo "  ✗ targets file not found at $TARGETS"
  echo "    Cannot verify PHI. Resolve before close-out (do NOT skip)."
  fail=1
else
  # This is a FAST TRIPWIRE, not the authoritative detector. The deep fuzzy
  # battery (OCR-variant / boundary-defeating matching) lives in the sanitizer
  # repo. Pattern generation is shared with the pre-commit gate and lives in
  # phi-patterns.py: distinctive raw IDs (substring), full multi-token
  # names/addresses (whole-word), PLUS runtime-derived encoded variants
  # (URL-encoded, plus-encoded, %5E HL7-delimited, digit-compact) — the exact
  # escape classes from the 2026-06-11 leak. PATTERN values are fed to grep
  # via temp files and never echoed.
  PATFILE="$(mktemp)"; SUB="$(mktemp)"; WORD="$(mktemp)"
  python3 "$ROOT/.claude/scripts/phi-patterns.py" "$TARGETS" > "$PATFILE"
  # split into mode-specific pattern files (values stay in files, never echoed)
  while IFS=$'\t' read -r mode pat; do
    [[ -z "$pat" ]] && continue
    if [[ "$mode" == "SUB" ]]; then printf '%s\n' "$pat" >> "$SUB"
    else printf '%s\n' "$pat" >> "$WORD"; fi
  done < "$PATFILE"
  npat=$(grep -c . "$PATFILE")
  hits=0
  if [[ -s "$SUB" ]]; then
    while IFS= read -r f; do echo "  ✗ $f  (distinctive-ID match)"; hits=$((hits+1)); done \
      < <(grep -RFilf "$SUB" wikis --include="*.md" 2>/dev/null)
  fi
  if [[ -s "$WORD" ]]; then
    while IFS= read -r f; do echo "  ✗ $f  (full name/address match)"; hits=$((hits+1)); done \
      < <(grep -RwFilf "$WORD" wikis --include="*.md" 2>/dev/null)
  fi
  rm -f "$PATFILE" "$SUB" "$WORD"
  if [[ $hits -eq 0 ]]; then
    echo "  ✓ no distinctive redaction targets present in wikis/ ($npat patterns checked, incl. encoded variants)"
    echo "    (fast tripwire only — the nightly leak scan / sanitizer fuzzy battery is the deep check)"
  else
    echo "  → $hits file hit(s). Re-run the sanitizer pass before close-out."
    fail=1
  fi
fi

# ---- 2. Duplicate "-source.md" artifacts ------------------------------------
echo
echo "[2/4] Stray '-source.md' duplicate artifacts"
read_lines srcdup < <(find wikis -name "*-source.md" 2>/dev/null)
if [[ ${#srcdup[@]} -eq 0 ]]; then
  echo "  ✓ none"
else
  printf '  ✗ %s\n' "${srcdup[@]}"
  echo "  → merge into the canonical page and delete, as in the 66-file batch cleanup."
  fail=1
fi

# ---- 3. Orphaned sidecars in ingest/ ----------------------------------------
echo
echo "[3/4] Orphaned .meta.json in ingest/"
read_lines orphans < <(find ingest -maxdepth 1 -name "*.meta.json" 2>/dev/null)
if [[ ${#orphans[@]} -eq 0 ]]; then
  echo "  ✓ none"
else
  printf '  ✗ %s\n' "${orphans[@]}"
  echo "  → move each sidecar to its transcript's destination (CLAUDE.md hard rule)."
  fail=1
fi

# ---- 4. Bracket-wrapped redaction placeholders (phantom graph nodes) --------
echo
echo "[4/4] Bracket-wrapped redaction placeholders ([[REDACTED-*]])"
read_lines wrapped < <(grep -rlE '\[\[REDACTED-[A-Z]+\]\]' wikis --include="*.md" 2>/dev/null)
if [[ ${#wrapped[@]} -eq 0 ]]; then
  echo "  ✓ none"
else
  printf '  ✗ %s\n' "${wrapped[@]}"
  echo "  → unwrap: perl -i -pe 's/\\[\\[(REDACTED-[A-Z]+)\\]\\]/\$1/g' <file>"
  fail=1
fi

echo
echo "================================================"
if [[ $fail -eq 0 ]]; then
  echo "RESULT: clean — safe to close out."
else
  echo "RESULT: findings above must be triaged before close-out."
fi
exit $fail
