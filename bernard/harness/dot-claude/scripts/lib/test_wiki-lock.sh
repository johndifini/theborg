#!/usr/bin/env bash
# test_wiki-lock.sh — unit tests for the shared wiki write-lock (lib/wiki-lock.sh).
# Run: bash .claude/scripts/lib/test_wiki-lock.sh   (exit 0 = all pass)
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
check(){ if eval "$2"; then ok "$1"; else bad "$1 [cond: $2]"; fi; }

# Isolated sandbox so we never touch the real lock.
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/wiki-lock-test.XXXXXX")"
export WIKI_LOCK_DIR="$SANDBOX/wiki-write.lock"
export WIKI_LOCK_ROOT="$SANDBOX"
export WIKI_LOCK_TTL=2          # short TTL so staleness is testable
trap 'rm -rf "$SANDBOX"' EXIT

source "$DIR/wiki-lock.sh"

echo "== wiki-lock unit tests =="

# 1. starts free
check "free before acquire"            'wiki_lock_active; [ $? -eq 1 ]'

# 2. acquire succeeds + records metadata
wiki_lock_acquire "tester-A"; rc=$?
check "acquire returns 0"              "[ $rc -eq 0 ]"
check "active after acquire"           'wiki_lock_active'
check "holder recorded"                '[ "$(wiki_lock_holder)" = "tester-A" ]'

# 3. second acquire by another is refused while fresh
wiki_lock_acquire "tester-B"; rc=$?
check "second acquire refused"         "[ $rc -eq 1 ]"
check "holder unchanged (still A)"     '[ "$(wiki_lock_holder)" = "tester-A" ]'

# 4. release frees it
wiki_lock_release
check "free after release"             'wiki_lock_active; [ $? -eq 1 ]'

# 5. re-acquire after release works
wiki_lock_acquire "tester-C"; rc=$?
check "re-acquire returns 0"           "[ $rc -eq 0 ]"

# 6. stale lock (older than TTL) is reclaimed automatically
sleep 3                                 # > WIKI_LOCK_TTL (2s)
check "stale lock treated as free"     'wiki_lock_active; [ $? -eq 1 ]'
wiki_lock_acquire "tester-D"; rc=$?
check "acquire over stale lock works"  "[ $rc -eq 0 ]"
check "holder is the reclaimer (D)"    '[ "$(wiki_lock_holder)" = "tester-D" ]'
wiki_lock_release

# 7. release is idempotent
wiki_lock_release; wiki_lock_release
check "double release is safe"         '[ $? -eq 0 ]'

echo
echo "== $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
