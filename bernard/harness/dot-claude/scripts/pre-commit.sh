#!/usr/bin/env bash
# pre-commit gate for the life wiki — the last mechanical check before
# anything enters git history. Unlike Claude-Code hooks, this covers EVERY
# committer: Claude, Codex, Gemini, and the curator's manual commits.
#
# Tracked copy: .claude/scripts/pre-commit.sh
# Installed at: .git/hooks/pre-commit  (reinstall after clone with:
#   cp .claude/scripts/pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit)
#
# Checks (staged content only — fast):
#   1. audio binaries (voice-biometric hard rule) — extension + file magic
#   2. distinctive PHI targets incl. encoded variants — values never printed
#   3. sidecar pairing — no .meta.json in the commit without its sibling .md
#
# Exit nonzero aborts the commit, naming only the failing section.
# Bypass (curator only, deliberate): git commit --no-verify
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)" || exit 0
cd "$ROOT" || exit 0
TARGETS="$HOME/Devops/life-wiki-sanitizer/secrets/redaction_targets.json"
PATGEN=".claude/scripts/phi-patterns.py"

staged=$(git diff --cached --name-only --diff-filter=ACMR)
deleted=$(git diff --cached --name-only --diff-filter=D)
[[ -z "$staged" && -z "$deleted" ]] && exit 0

fail=0

# ---- 1. Audio binaries -------------------------------------------------------
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  ext=$(printf '%s' "${f##*.}" | tr '[:upper:]' '[:lower:]')
  case "$ext" in
    m4a|mp3|wav|mp4|aac)
      echo "BLOCK [audio]: staged audio binary: $f"; fail=1 ;;
    md|json|txt|yaml|yml|csv|sh|py) ;;   # text — skip the magic check
    *)
      if [[ -f "$f" ]]; then
        mt=$(file -b --mime-type "$f" 2>/dev/null || true)
        case "$mt" in
          audio/*|video/mp4)
            echo "BLOCK [audio]: staged file has audio mime ($mt): $f"; fail=1 ;;
        esac
      fi ;;
  esac
done <<< "$staged"

# ---- 2. PHI tripwire on staged content ---------------------------------------
if [[ ! -f "$TARGETS" ]]; then
  echo "BLOCK [phi]: targets file not found at $TARGETS — cannot verify staged"
  echo "  content. Fix the sanitizer checkout, or bypass deliberately with --no-verify."
  fail=1
elif [[ ! -f "$PATGEN" ]]; then
  echo "BLOCK [phi]: $PATGEN missing — cannot generate patterns."
  fail=1
else
  SUBP="$(mktemp)"; WORDP="$(mktemp)"; CONTENT="$(mktemp)"
  trap 'rm -f "$SUBP" "$WORDP" "$CONTENT"' EXIT
  python3 "$PATGEN" "$TARGETS" | awk -F'\t' -v s="$SUBP" -v w="$WORDP" \
    '$1=="SUB"{print $2 > s} $1=="WORD"{print $2 > w}'
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    case "$f" in *.md|*.json|*.txt|*.yaml|*.yml|*.csv) ;; *) continue ;; esac
    git show ":$f" > "$CONTENT" 2>/dev/null || continue
    hit=""
    [[ -s "$SUBP" ]] && grep -qFf "$SUBP" "$CONTENT" && hit=1
    [[ -z "$hit" && -s "$WORDP" ]] && grep -qwFf "$WORDP" "$CONTENT" && hit=1
    if [[ -n "$hit" ]]; then
      echo "BLOCK [phi]: PHI tripwire match in staged $f (values not shown)"
      echo "  → unstage, re-run the sanitizer pass, see post-ingest-verify.sh"
      fail=1
    fi
  done <<< "$staged"
fi

# ---- 3. Sidecar pairing ------------------------------------------------------
# A .meta.json must never enter the commit without its sibling .md (the index
# is exactly what the commit will contain, so check against it).
while IFS= read -r f; do
  [[ "$f" == *.meta.json ]] || continue
  case "$f" in ingest/*|wikis/*) ;; *) continue ;; esac
  md="${f%.meta.json}.md"
  if ! git ls-files --error-unmatch "$md" >/dev/null 2>&1; then
    echo "BLOCK [sidecar]: $f staged without sibling $md (move both together — hard rule)"
    fail=1
  fi
done <<< "$staged"
# Deleting a .md while leaving its sidecar behind orphans it.
while IFS= read -r f; do
  [[ "$f" == *.md ]] || continue
  sc="${f%.md}.meta.json"
  if git ls-files --error-unmatch "$sc" >/dev/null 2>&1 \
     && ! git diff --cached --name-only --diff-filter=D | grep -qxF "$sc"; then
    echo "BLOCK [sidecar]: deleting $f orphans $sc (delete or move both together)"
    fail=1
  fi
done <<< "$deleted"

if [[ $fail -ne 0 ]]; then
  echo
  echo "pre-commit gate failed — fix the BLOCK items above."
  echo "Deliberate curator bypass only: git commit --no-verify"
fi
exit $fail
