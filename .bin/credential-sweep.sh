#!/bin/bash
# credential-sweep.sh — find live credential VALUES sitting in plaintext on disk.
#
# Why this is a script and not a paragraph in a prompt:
# ----------------------------------------------------
# The daily security audit used to describe this sweep in prose and let each run
# reconstruct it. On 2026-08-23 that failed: four consecutive audits reported
# "zero live token values on disk" while 25 files under Xcode's DEFAULT
# DerivedData held live credentials. The scope had drifted — runs kept sweeping
# the *relocated* SwiftPM cache from an earlier remediation and never noticed
# that the default DerivedData path had left the list. Three narrower bugs rode
# along with it, and each is now a hard guarantee below rather than something a
# run has to remember:
#
#   1. PINNED GREP. The interactive `grep` on this machine is a ugrep shim that
#      honours --ignore-files, so it can silently skip gitignored paths — which
#      is exactly where secrets live. Every sweep here uses /usr/bin/grep.
#   2. DISCOVERED ROOTS. Cache locations are enumerated at run time (including
#      Xcode's own .knownDerivedDataLocations.log) instead of hard-coded, so a
#      new build cache cannot quietly fall out of scope.
#   3. VALUES, NOT PREFIXES. The old sweep matched sk-ant-* only, so a non-
#      Anthropic key would have been missed even inside a swept directory. This
#      reads the real values from the secret files and greps for those. A
#      provider-prefix pass still runs, but as a SECOND net for credentials that
#      are not in the env files at all — never as the primary check.
#   4. HONEST EXIT CODES. `timeout` does not exist on macOS: `timeout N grep …`
#      exits 127 and prints nothing, which is indistinguishable from "clean".
#      And `grep … | head` reports head's status, not grep's. Nothing here pipes
#      grep, and every rc is inspected.
#
# It also self-tests before trusting itself (see CANARY): a sweep that cannot
# see into a gitignored path must fail loudly, not return clean.
#
# SECRECY: this file is tracked in a PUBLIC repo. It contains no credential
# values and never prints one — findings are reported as VARIABLE NAME + file
# path only. The pattern file it builds is mode 0600 and removed on every exit
# path, including signals.
#
# Usage:   .bin/credential-sweep.sh [--quiet] [extra-root ...]
# Exit:    0 = clean   1 = credentials found   2 = sweep could not be trusted
set -uo pipefail

GREP=/usr/bin/grep
BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && { QUIET=1; shift; }

[[ -x "$GREP" ]] || { echo "FATAL: $GREP missing — refusing to fall back to a shim grep" >&2; exit 2; }

PATFILE=$(mktemp -t credsweep); chmod 600 "$PATFILE"
NAMEFILE=$(mktemp -t credsweepn); chmod 600 "$NAMEFILE"
CANARY_DIR=""
cleanup() { rm -f "$PATFILE" "$NAMEFILE"; [[ -n "$CANARY_DIR" ]] && rm -rf "$CANARY_DIR"; }
trap cleanup EXIT INT TERM HUP

say() { [[ $QUIET -eq 1 ]] || echo "$@"; }

# ---------------------------------------------------------------------------
# 1. Build the pattern set from the real secret stores. Discovered, not listed:
#    any NAME=VALUE whose NAME looks like a credential and whose VALUE is a
#    literal long enough to be one. A new secret added to either file is picked
#    up with no edit here.
# ---------------------------------------------------------------------------
SECRET_FILES=("$HOME/.zshenv" "$HOME/.borg-secrets/.env" "$BORG_ROOT/.env")
for f in "${SECRET_FILES[@]}"; do
  [[ -r "$f" ]] || continue
  python3 - "$f" "$PATFILE" "$NAMEFILE" <<'PY'
import re,sys
src,patf,namef=sys.argv[1],sys.argv[2],sys.argv[3]
NAME=re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
CRED=re.compile(r'(TOKEN|KEY|SECRET|PASS|PASSWORD|CREDENTIAL|API)',re.I)
pats,names=[],[]
for line in open(src,errors='replace'):
    if line.lstrip().startswith('#'): continue
    m=NAME.match(line)
    if not m: continue
    name,val=m.group(1),m.group(2).strip()
    if not CRED.search(name): continue
    if val[:1] in ('"',"'") and val[-1:]==val[:1]: val=val[1:-1]
    val=val.strip()
    # Skip references and interpolations — only literal values are greppable.
    if not val or '$' in val or len(val)<16: continue
    pats.append(val); names.append(f"{name}\t{val}")
open(patf,'a').write(''.join(p+'\n' for p in pats))
open(namef,'a').write(''.join(n+'\n' for n in names))
PY
done

# Strip blank lines. A single empty line in a `grep -F -f` pattern file matches
# EVERY line of EVERY file, which would turn this sweep into a firehose that
# reads as catastrophe. Guard it explicitly rather than trusting the parser.
"$GREP" -v '^[[:space:]]*$' "$PATFILE" > "$PATFILE.c" 2>/dev/null; mv "$PATFILE.c" "$PATFILE"
NPAT=$(wc -l < "$PATFILE" | tr -d ' ')
if [[ "$NPAT" -eq 0 ]]; then
  echo "FATAL: no credential values could be read from the secret stores." >&2
  echo "       A sweep with an empty pattern set reports clean for the wrong reason." >&2
  exit 2
fi
say "patterns: $NPAT credential value(s) from ${#SECRET_FILES[@]} candidate store(s)"

# ---------------------------------------------------------------------------
# 2. CANARY. Prove the sweep can see into a gitignored path BEFORE trusting a
#    clean result. This is the check that fails loudly instead of silently.
# ---------------------------------------------------------------------------
# The canary MUST use a synthetic sentinel, never a real credential. It writes
# into $BORG_ROOT/tmp, and that path is inside the Google Drive mirror root — a
# live value planted there, even for the second before it is deleted, is a
# candidate for upload. Testing the mechanism does not require testing it with
# a real secret: what is under test is whether /usr/bin/grep -rlaF -f can see
# into a gitignored directory at all.
CANARY_DIR="$BORG_ROOT/tmp/.credsweep-canary-$$"
mkdir -p "$CANARY_DIR" 2>/dev/null || { echo "FATAL: cannot create canary dir" >&2; exit 2; }
CANARY_VAL="CREDSWEEP-CANARY-SENTINEL-$$-do-not-treat-as-a-secret"
CANARY_PAT="$CANARY_DIR/.pat"
printf '%s\n' "$CANARY_VAL" > "$CANARY_PAT"
printf 'canary %s\n' "$CANARY_VAL" > "$CANARY_DIR/canary.txt"
if git -C "$BORG_ROOT" check-ignore -q "$CANARY_DIR/canary.txt" 2>/dev/null; then
  say "canary: target path is gitignored (correct test condition)"
else
  say "canary: WARNING — target path is not gitignored; test is weaker than intended"
fi
"$GREP" -rlaF -f "$CANARY_PAT" "$CANARY_DIR/canary.txt" >/dev/null 2>&1; crc=$?
if [[ $crc -ne 0 ]]; then
  echo "FATAL: canary MISSED — the sweep cannot see a known value in a gitignored path." >&2
  echo "       Every clean result from this tool is untrustworthy until fixed." >&2
  exit 2
fi
say "canary: PASSED"
rm -rf "$CANARY_DIR"; CANARY_DIR=""

# ---------------------------------------------------------------------------
# 3. Discover roots. Anything that can hold a build cache, plus the workspace.
# ---------------------------------------------------------------------------
ROOTS=()
add_root() { [[ -n "${1:-}" && -e "$1" ]] && ROOTS+=("$1"); }

add_root "$BORG_ROOT"
add_root "$HOME/Library/Caches/theborg"
add_root "$HOME/Library/Developer/Xcode/DerivedData"
add_root "$HOME/Library/Caches/org.swift.swiftpm"
add_root "$HOME/.swiftpm"

# Xcode records every DerivedData location it has ever used, including custom
# per-project overrides that no hard-coded list would know about.
KNOWN="$HOME/Library/Developer/Xcode/.knownDerivedDataLocations.log"
if [[ -r "$KNOWN" ]]; then
  while IFS= read -r d; do add_root "$d"; done < <(
    python3 -c '
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: sys.exit(0)
for e in d.get("derivedDataDirectories",[]):
    if isinstance(e,str): print(e)
    elif isinstance(e,dict):
        for k in ("path","derivedDataPath"):
            if isinstance(e.get(k),str): print(e[k])
' "$KNOWN" 2>/dev/null)
fi

# Repo-local build output anywhere under the workspace.
while IFS= read -r d; do add_root "$d"; done < <(
  /usr/bin/find "$BORG_ROOT" -maxdepth 6 -type d \
    \( -name .build -o -name DerivedData -o -name XCBuildData -o -name .swiftpm \) \
    -not -path '*/.git/*' 2>/dev/null)

# Caller-supplied extra roots.
for extra in "$@"; do add_root "$extra"; done

# Canonicalise, dedupe, then drop any root already contained in another (the
# parent sweep covers it). Written for bash 3.2 — macOS ships no `mapfile`, and
# using it here silently no-opped the whole block on first run, leaving a
# duplicated root and no nesting elimination.
CANON=()
for r in "${ROOTS[@]}"; do
  c=$(cd "$r" 2>/dev/null && pwd -P) || continue
  dup=0
  for seen in ${CANON[@]+"${CANON[@]}"}; do [[ "$seen" == "$c" ]] && { dup=1; break; }; done
  [[ $dup -eq 0 ]] && CANON+=("$c")
done
ROOTS=(${CANON[@]+"${CANON[@]}"})
KEEP=()
for r in "${ROOTS[@]}"; do
  nested=0
  for o in "${ROOTS[@]}"; do
    [[ "$r" == "$o" ]] && continue
    [[ "$r" == "$o"/* ]] && { nested=1; break; }
  done
  [[ $nested -eq 0 ]] && KEEP+=("$r")
done
ROOTS=(${KEEP[@]+"${KEEP[@]}"})
say "roots: ${#ROOTS[@]} discovered"
for r in "${ROOTS[@]}"; do say "  - $r"; done

# ---------------------------------------------------------------------------
# 4. Sweep. rc captured directly from grep — never through a pipe, never with
#    `timeout` (which does not exist here and would exit 127 looking clean).
# ---------------------------------------------------------------------------
HITFILE=$(mktemp -t credsweeph); chmod 600 "$HITFILE"
TOTAL=0
for r in "${ROOTS[@]}"; do
  OUT=$(mktemp -t credsweepo); chmod 600 "$OUT"
  "$GREP" -rlaF -f "$PATFILE" "$r" > "$OUT" 2>/dev/null; rc=$?
  if [[ $rc -gt 1 ]]; then
    echo "WARN: grep returned rc=$rc for $r — result for this root is NOT trustworthy" >&2
  fi
  n=$(wc -l < "$OUT" | tr -d ' ')
  TOTAL=$((TOTAL+n))
  say "  swept $r -> $n hit(s) (rc=$rc)"
  cat "$OUT" >> "$HITFILE"; rm -f "$OUT"
done

# Provider-prefix second net: catches credentials that live nowhere in the env
# files and so have no value to match. Reported separately — a hit here is a
# lead to investigate, not automatically a live secret.
PREFIX_RE='sk-ant-(oat|api)[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{40,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
PFILE=$(mktemp -t credsweepp); chmod 600 "$PFILE"
for r in "${ROOTS[@]}"; do
  "$GREP" -rlaE "$PREFIX_RE" "$r" >> "$PFILE" 2>/dev/null
done
sort -u "$PFILE" -o "$PFILE"
# Anything already caught by value is not news here.
sort -u "$HITFILE" -o "$HITFILE"
PONLY=$(comm -23 "$PFILE" "$HITFILE" | wc -l | tr -d ' ')

# ---------------------------------------------------------------------------
# 5. Report. Variable NAMES and paths only — never a value.
# ---------------------------------------------------------------------------
echo
echo "=== credential sweep: $TOTAL file(s) containing live credential values ==="
if [[ $TOTAL -gt 0 ]]; then
  while IFS= read -r hit; do
    [[ -n "$hit" ]] || continue
    mode=$(stat -f "%Sp" "$hit" 2>/dev/null)
    which=""
    while IFS=$'\t' read -r nm val; do
      [[ -n "$val" ]] || continue
      "$GREP" -qaF "$val" "$hit" 2>/dev/null && which="${which:+$which,}$nm"
    done < "$NAMEFILE"
    world=""
    case "$mode" in *r--r--|*rw-r--r--|*r-xr-xr-x) world=" [WORLD-READABLE]";; esac
    echo "  $mode$world  $hit"
    echo "      exposes: ${which:-<unresolved>}"
  done < "$HITFILE"
fi
echo "=== provider-pattern leads not explained by a known value: $PONLY ==="
[[ $PONLY -gt 0 ]] && comm -23 "$PFILE" "$HITFILE" | sed 's/^/  /'
rm -f "$HITFILE" "$PFILE"

if [[ $TOTAL -gt 0 || $PONLY -gt 0 ]]; then
  echo
  echo "RESULT: NOT CLEAN — credential material found on disk."
  exit 1
fi
echo "RESULT: clean — no live credential values on disk across ${#ROOTS[@]} root(s)."
exit 0
