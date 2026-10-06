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
#   5. JSON STORES TOO. Added 2026-09-03 for security-audit finding 17. Not every
#      credential store is a shell env file: the Vercel CLI writes a deploy token
#      and a refresh token into a JSON file under ~/Library. That store was doubly
#      invisible here — wrong path AND a shape the NAME=VALUE parser cannot read —
#      so a Vercel token leaking into a build cache would have swept clean. JSON
#      stores are now a first-class store class with the same rules: keys matching
#      the credential-name regex, values long enough to be real, names-only output.
#   6. LARGE FILES GO TO A CHUNKED SCANNER, NOT GREP. Added 2026-10-05 for
#      security-audit finding 38. An Xcode GUI build created sparse files in
#      DerivedData/CompilationCache.noindex with 37 GB of apparent size but ~16 KB
#      allocated each. grep reads every zero (about 10 s/GB, worse on the 24 GB
#      file), so the sweep ran past the audit's time budget, was killed, and
#      produced no verdict. APFS reports the whole file as one data region, so
#      SEEK_DATA cannot skip the holes. Files above LARGE_BYTES are therefore
#      scanned in chunks by Python, which discards all-zero chunks cheaply. They
#      are SCANNED, not skipped, and each one is listed in the output so the
#      scope stays visible. Any grep, find, or scanner error now makes the exit
#      code 2. It used to print a warning and still exit 0.
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
# Env:     CREDSWEEP_LARGE_BYTES  size above which a file goes to the chunked
#          scanner instead of grep (default 268435456 = 256 MiB)
# Exit:    0 = clean   1 = credentials found   2 = sweep could not be trusted
#          (2 wins over 1: credentials found during an untrusted sweep are
#          still listed, but the run is reported as untrusted)
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

# ---------------------------------------------------------------------------
# 1b. JSON credential stores. Same discovery principle as above — a key whose
#     NAME looks like a credential and whose string value is long enough to be
#     one — applied to nested JSON rather than NAME=VALUE lines.
#
#     A store that is ABSENT is skipped silently: not every machine has the
#     Vercel CLI, and a missing optional store is not a failure. A store that is
#     PRESENT but unparseable is FATAL. That asymmetry is the whole point: the
#     bug this class exists to fix was a store we could not see reporting clean,
#     so being unable to read a store that is sitting right there must never
#     degrade into a clean result.
# ---------------------------------------------------------------------------
JSON_SECRET_FILES=("$HOME/Library/Application Support/com.vercel.cli/auth.json")
# The `${a[@]+"${a[@]}"}` guard is not decoration: macOS ships bash 3.2, where an
# empty array expanded under `set -u` is an "unbound variable" fatal, so emptying
# this list would crash the sweep rather than skip the class.
for f in ${JSON_SECRET_FILES[@]+"${JSON_SECRET_FILES[@]}"}; do
  [[ -r "$f" ]] || continue
  before=$(wc -l < "$NAMEFILE" | tr -d ' ')
  python3 - "$f" "$PATFILE" "$NAMEFILE" <<'PY'
import json,os,re,sys
src,patf,namef=sys.argv[1],sys.argv[2],sys.argv[3]
CRED=re.compile(r'(TOKEN|KEY|SECRET|PASS|PASSWORD|CREDENTIAL|API)',re.I)
try:
    with open(src,errors='replace') as fh: data=json.load(fh)
except Exception as e:
    sys.stderr.write("  json store unreadable (%s)\n" % e.__class__.__name__)
    sys.exit(1)
# Label the finding by store + key path, never by value.
label=os.path.join(os.path.basename(os.path.dirname(src)),os.path.basename(src))
pats,names=[],[]
def walk(node,path):
    if isinstance(node,dict):
        for k,v in node.items(): walk(v,path+[str(k)])
    elif isinstance(node,list):
        for i,v in enumerate(node): walk(v,path+[str(i)])
    elif isinstance(node,str):
        if not path or not CRED.search(path[-1]): return
        val=node.strip()
        if len(val)<16: return
        pats.append(val); names.append("%s:%s\t%s"%(label,".".join(path),val))
walk(data,[])
open(patf,'a').write(''.join(p+'\n' for p in pats))
open(namef,'a').write(''.join(n+'\n' for n in names))
PY
  if [[ $? -ne 0 ]]; then
    echo "FATAL: JSON credential store is present but could not be parsed:" >&2
    echo "       $f" >&2
    echo "       Refusing to report clean while blind to a store that exists." >&2
    exit 2
  fi
  after=$(wc -l < "$NAMEFILE" | tr -d ' ')
  # A logged-out CLI legitimately yields 0. Say so rather than staying silent,
  # so a store that has quietly stopped contributing is visible in the report.
  say "json store: $f -> $((after-before)) credential value(s)"
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
say "patterns: $NPAT credential value(s) from $(( ${#SECRET_FILES[@]} + ${#JSON_SECRET_FILES[@]} )) candidate store(s)"

# ---------------------------------------------------------------------------
# 1c. Scan engines. The canary below runs both of them before any real root.
#
#     grep_root  — every regular file at or below LARGE_BYTES, through
#                  /usr/bin/grep in fixed-size batches. Each batch is a direct
#                  call, so its rc is grep's own. There is no xargs, which folds
#                  "no match" and "error" into a single code.
#     scan_large — every file above LARGE_BYTES, read in 64 MiB chunks by
#                  Python. All-zero chunks are discarded before matching, which
#                  is what makes sparse caches cheap. Values are read from the
#                  0600 name file outside the mirror and held in memory only.
#
#     Both return 2 when anything they ran was not trustworthy.
# ---------------------------------------------------------------------------
LARGE_BYTES="${CREDSWEEP_LARGE_BYTES:-268435456}"
[[ "$LARGE_BYTES" =~ ^[0-9]+$ ]] || { echo "FATAL: CREDSWEEP_LARGE_BYTES must be a byte count" >&2; exit 2; }
BATCH=400
# Provider-prefix second net: catches credentials that live nowhere in the env
# files and so have no value to match. Reported separately — a hit here is a
# lead to investigate, not automatically a live secret.
PREFIX_RE='sk-ant-(oat|api)[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{40,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[0-9A-Za-z-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----'

# grep_batch ROOT OUTFILE GREP-MATCH-ARGS...  — greps the caller's ${batch[@]}.
# The workspace is edited concurrently, so a file can vanish between find and
# grep, and grep then returns 2 for a file that no longer exists. A vanished
# file cannot hold a credential, so on rc>1 the batch is retried once with only
# the files that still exist. A second failure is real: grep's own error lines
# (paths, never values) are printed and the root is marked untrustworthy.
grep_batch() {
  local root=$1 out=$2; shift 2
  local err tout rc f kept=()
  err=$(mktemp -t credsweepe); chmod 600 "$err"
  tout=$(mktemp -t credsweepo); chmod 600 "$tout"
  "$GREP" -la "$@" -- "${batch[@]}" > "$tout" 2> "$err"; rc=$?
  if [[ $rc -gt 1 ]]; then
    for f in "${batch[@]}"; do [[ -e "$f" ]] && kept+=("$f"); done
    if [[ ${#kept[@]} -lt ${#batch[@]} ]]; then
      say "  note: $(( ${#batch[@]} - ${#kept[@]} )) file(s) under $root vanished mid-sweep; batch retried"
    fi
    rc=1
    if [[ ${#kept[@]} -gt 0 ]]; then
      "$GREP" -la "$@" -- "${kept[@]}" > "$tout" 2> "$err"; rc=$?
    else
      : > "$tout"
    fi
    if [[ $rc -gt 1 ]]; then
      echo "WARN: grep returned rc=$rc under $root, after a retry:" >&2
      sed -n '1,5s/^/       /p' "$err" >&2
    fi
  fi
  cat "$tout" >> "$out"
  rm -f "$err" "$tout"
  [[ $rc -le 1 ]]
}

# grep_root ROOT OUTFILE GREP-MATCH-ARGS...  (appends matching paths to OUTFILE)
grep_root() {
  local root=$1 out=$2; shift 2
  local list rc bad=0 f
  local batch=()
  list=$(mktemp -t credsweepl); chmod 600 "$list"
  /usr/bin/find "$root" -type f ! -size +"${LARGE_BYTES}"c -print0 > "$list" 2>/dev/null; rc=$?
  [[ $rc -ne 0 ]] && { echo "WARN: find returned rc=$rc under $root — listing is incomplete" >&2; bad=1; }
  while IFS= read -r -d '' f; do
    batch+=("$f")
    if [[ ${#batch[@]} -ge $BATCH ]]; then
      grep_batch "$root" "$out" "$@" || bad=1
      batch=()
    fi
  done < "$list"
  if [[ ${#batch[@]} -gt 0 ]]; then
    grep_batch "$root" "$out" "$@" || bad=1
  fi
  rm -f "$list"
  [[ $bad -eq 0 ]] || return 2
}

# scan_large ROOT THRESHOLD NAMEFILE VALOUT PREFIXOUT LISTOUT
#   VALOUT    gets "path<TAB>NAME,NAME" per file holding a known value
#   PREFIXOUT gets the paths that match PREFIX_RE
#   LISTOUT   gets every file it scanned, so the report can show the scope
scan_large() {
  local root=$1 thr=$2 names=$3 vout=$4 pout=$5 lout=$6 list rc
  list=$(mktemp -t credsweepl); chmod 600 "$list"
  /usr/bin/find "$root" -type f -size +"${thr}"c -print0 > "$list" 2>/dev/null; rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "WARN: find returned rc=$rc under $root (large files) — listing is incomplete" >&2
    rm -f "$list"; return 2
  fi
  python3 - "$names" "$list" "$vout" "$pout" "$lout" "$PREFIX_RE" <<'PY'
import re,sys
namef,listf,vout,pout,lout,prefix=sys.argv[1:7]
vals=[]
for line in open(namef,'rb'):
    line=line.rstrip(b'\n')
    if b'\t' not in line: continue
    n,v=line.split(b'\t',1)
    if v.strip(): vals.append((n.decode(errors='replace'),v))
if not vals:
    sys.stderr.write("WARN: large-file scanner loaded no values\n"); sys.exit(2)
rx=re.compile(prefix.encode())
CH=64<<20
OV=max(4096,max(len(v) for _,v in vals))   # overlap so no match straddles a chunk edge
bad=0
with open(vout,'ab') as V, open(pout,'ab') as P, open(lout,'ab') as L:
    for p in [x for x in open(listf,'rb').read().split(b'\0') if x]:
        hit=set(); pre=False; tail=b''
        try:
            with open(p,'rb') as fh:
                while True:
                    b=fh.read(CH)
                    if not b: break
                    buf=tail+b; tail=buf[-OV:]
                    if not buf.strip(b'\0'): continue   # sparse hole or zero fill
                    for n,v in vals:
                        if v in buf: hit.add(n)
                    if not pre and rx.search(buf): pre=True
        except OSError as e:
            sys.stderr.write("WARN: large-file scanner could not read %s (%s)\n"
                             % (p.decode(errors='replace'),e.__class__.__name__))
            bad=1; continue
        L.write(p+b'\n')
        if hit: V.write(p+b'\t'+','.join(sorted(hit)).encode()+b'\n')
        if pre: P.write(p+b'\n')
sys.exit(2 if bad else 0)
PY
  rc=$?; rm -f "$list"
  [[ $rc -eq 0 ]] || { echo "WARN: large-file scanner returned rc=$rc under $root" >&2; return 2; }
}

# ---------------------------------------------------------------------------
# 2. CANARY. Prove the sweep can see into a gitignored path BEFORE trusting a
#    clean result. This is the check that fails loudly instead of silently.
# ---------------------------------------------------------------------------
# The canary MUST use a synthetic sentinel, never a real credential. It writes
# into $BORG_ROOT/tmp, and that path is inside the Google Drive mirror root — a
# live value planted there, even for the second before it is deleted, is a
# candidate for upload. Testing the mechanism does not require testing it with
# a real secret: what is under test is whether each scan engine can see into a
# gitignored directory at all. Both engines are tested, because a root's files
# are split between them by size.
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
CANARY_NAMES="$CANARY_DIR/.names"
printf 'CREDSWEEP_CANARY\t%s\n' "$CANARY_VAL" > "$CANARY_NAMES"
CG=$(mktemp -t credsweepc); CV=$(mktemp -t credsweepc); CX=$(mktemp -t credsweepc); CL=$(mktemp -t credsweepc)
grep_root "$CANARY_DIR" "$CG" -F -f "$CANARY_PAT"; grc=$?
# Threshold 0 forces every canary file through the large-file engine too.
scan_large "$CANARY_DIR" 0 "$CANARY_NAMES" "$CV" "$CX" "$CL"; lrc=$?
"$GREP" -qxF "$CANARY_DIR/canary.txt" "$CG"; gseen=$?
"$GREP" -qF "$CANARY_DIR/canary.txt"$'\t'"CREDSWEEP_CANARY" "$CV"; lseen=$?
rm -f "$CG" "$CV" "$CX" "$CL"
if [[ $grc -ne 0 || $gseen -ne 0 || $lrc -ne 0 || $lseen -ne 0 ]]; then
  echo "FATAL: canary MISSED — the sweep cannot see a known value in a gitignored path" >&2
  echo "       (grep engine rc=$grc seen=$((gseen==0)); large-file engine rc=$lrc seen=$((lseen==0)))." >&2
  echo "       Every clean result from this tool is untrustworthy until fixed." >&2
  exit 2
fi
say "canary: PASSED (grep engine and large-file engine)"
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
HITFILE=$(mktemp -t credsweeph); chmod 600 "$HITFILE"   # grep-engine value hits
LHIT=$(mktemp -t credsweeph); chmod 600 "$LHIT"          # large-file value hits: path<TAB>names
PFILE=$(mktemp -t credsweepp); chmod 600 "$PFILE"        # provider-prefix leads, both engines
LLIST=$(mktemp -t credsweepl); chmod 600 "$LLIST"        # every large file scanned
UNTRUSTED=0
for r in "${ROOTS[@]}"; do
  hb=$(wc -l < "$HITFILE"); lb=$(wc -l < "$LHIT"); sb=$(wc -l < "$LLIST")
  ok=1
  grep_root "$r" "$HITFILE" -F -f "$PATFILE"                       || ok=0
  scan_large "$r" "$LARGE_BYTES" "$NAMEFILE" "$LHIT" "$PFILE" "$LLIST" || ok=0
  grep_root "$r" "$PFILE" -E -e "$PREFIX_RE"                       || ok=0
  n=$(( $(wc -l < "$HITFILE") - hb + $(wc -l < "$LHIT") - lb ))
  big=$(( $(wc -l < "$LLIST") - sb ))
  if [[ $ok -eq 1 ]]; then state="trusted"; else state="NOT TRUSTWORTHY"; UNTRUSTED=1; fi
  say "  swept $r -> $n hit(s), $big large file(s) chunk-scanned ($state)"
done

sort -u "$PFILE" -o "$PFILE"
sort -u "$HITFILE" -o "$HITFILE"
ALLHITS=$(mktemp -t credsweeph); chmod 600 "$ALLHITS"
{ cat "$HITFILE"; cut -f1 "$LHIT"; } | sort -u > "$ALLHITS"
TOTAL=$(wc -l < "$ALLHITS" | tr -d ' ')
# Anything already caught by value is not news here.
PONLY=$(comm -23 "$PFILE" "$ALLHITS" | wc -l | tr -d ' ')

# ---------------------------------------------------------------------------
# 5. Report. Variable NAMES and paths only — never a value.
# ---------------------------------------------------------------------------
echo
NBIG=$(wc -l < "$LLIST" | tr -d ' ')
echo "=== large files scanned in chunks instead of grep (> $LARGE_BYTES bytes): $NBIG ==="
while IFS= read -r big; do
  [[ -n "$big" ]] || continue
  echo "  $(stat -f '%z bytes apparent, %b blocks' "$big" 2>/dev/null)  $big"
done < "$LLIST"
echo "=== credential sweep: $TOTAL file(s) containing live credential values ==="
if [[ $TOTAL -gt 0 ]]; then
  while IFS= read -r hit; do
    [[ -n "$hit" ]] || continue
    mode=$(stat -f "%Sp" "$hit" 2>/dev/null)
    # Large files were already attributed by the chunked scanner; re-grepping
    # them per value would reintroduce the stall this split exists to avoid.
    which=$(awk -F'\t' -v p="$hit" '$1==p {print $2; exit}' "$LHIT")
    if [[ -z "$which" ]]; then
      while IFS=$'\t' read -r nm val; do
        [[ -n "$val" ]] || continue
        "$GREP" -qaF "$val" "$hit" 2>/dev/null && which="${which:+$which,}$nm"
      done < "$NAMEFILE"
    fi
    world=""
    case "$mode" in *r--r--|*rw-r--r--|*r-xr-xr-x) world=" [WORLD-READABLE]";; esac
    echo "  $mode$world  $hit"
    echo "      exposes: ${which:-<unresolved>}"
  done < "$ALLHITS"
fi
echo "=== provider-pattern leads not explained by a known value: $PONLY ==="
[[ $PONLY -gt 0 ]] && comm -23 "$PFILE" "$ALLHITS" | sed 's/^/  /'
rm -f "$HITFILE" "$LHIT" "$PFILE" "$LLIST" "$ALLHITS"

if [[ $UNTRUSTED -ne 0 ]]; then
  echo
  echo "RESULT: UNTRUSTED — at least one root could not be swept reliably (see WARN lines)."
  [[ $TOTAL -gt 0 || $PONLY -gt 0 ]] && echo "        Credential material WAS also found above; treat it as real."
  exit 2
fi
if [[ $TOTAL -gt 0 || $PONLY -gt 0 ]]; then
  echo
  echo "RESULT: NOT CLEAN — credential material found on disk."
  exit 1
fi
echo "RESULT: clean — no live credential values on disk across ${#ROOTS[@]} root(s)."
exit 0
