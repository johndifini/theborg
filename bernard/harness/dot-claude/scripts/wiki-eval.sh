#!/usr/bin/env bash
# wiki-eval.sh — golden-question eval harness over wiki-query + GBrain graph.
#
# Deterministic bash, no model calls. Runs the golden set in
# .claude/reference/eval-questions.tsv and:
#   - logs results to .claude/logs/wiki-eval.log
#   - writes .claude/logs/wiki-eval-status  ("pass P/T fail:<ids> orphans:<n> <ts>")
#   - NEW failures (vs previous status) are appended to the question inbox
#     tagged [eval][Qxx] so /inbox-triage turns them into graph fixes —
#     the eval and the wiki improve each other.
#
# Scheduled DAILY at 09:15 by com.life-wiki.eval (was 3x daily until 2026-07-02).
# Manual run: bash .claude/scripts/wiki-eval.sh
# Note: first semantic query after >60 min idle cold-starts Ollama (2-5 min) —
# normal, not a hang. PGLite lock contention with the 15-min gbrain-sync is
# handled by retries.
set -uo pipefail

WIKI="/Users/lashawsalta/life-wiki"
LOGDIR="$WIKI/.claude/logs"
STATUS="$LOGDIR/wiki-eval-status"
QFILE="$WIKI/.claude/reference/eval-questions.tsv"
GBRAIN="$WIKI/.claude/scripts/gbrain"
WQ="$WIKI/.claude/scripts/wiki-query"
INBOX="$WIKI/.claude/inbox/wiki-question-inbox.md"
ARCHIVE="$WIKI/.claude/inbox/inbox-archive.md"
LOCK="$WIKI/.claude/tmp/wiki-eval.lock"

mkdir -p "$LOGDIR" "$WIKI/.claude/tmp"
source "$WIKI/.claude/scripts/lib/wikilog.sh"
wikilog_open "wiki-eval"
LOG="$WIKILOG_BUF"
trap 'wikilog_flush' EXIT

# --build-links: when a graph golden-row fails, a missing edge is often just a
# declared-but-unlinked relationship. Build those edges mechanically, reindex,
# and re-test — only genuinely-missing connections then get filed. OFF by default
# so the 3x-daily scheduled run stays read-only/fast; the daily harness chain
# builds links proactively via build-graph-links.sh instead.
BUILD_LINKS=0
for a in "$@"; do case "$a" in --build-links) BUILD_LINKS=1 ;; esac; done

log()    { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
notify() { /usr/bin/osascript -e "display notification \"$1\" with title \"Wiki Eval\" sound name \"Ping\"" 2>/dev/null || true; }

# Single-flight; clear a stale lock (>2 h) like the mirror sync does.
if [[ -d "$LOCK" ]]; then
  if (( $(date +%s) - $(stat -f %m "$LOCK") > 7200 )); then rmdir "$LOCK" 2>/dev/null || true
  else log "another eval is running — exiting"; exit 0; fi
fi
mkdir "$LOCK" || exit 0
trap 'rmdir "$LOCK" 2>/dev/null; wikilog_flush' EXIT

[[ -f "$QFILE" ]] || { log "ERROR: $QFILE missing"; exit 1; }
log "=== wiki-eval run started ==="

# Warm-up: the first query after >60 min idle cold-starts Ollama (2-5 min), and
# the gbrain process only exits via its timeout. Pay full price once here, then
# cap every golden-set query at 90 s — results stream out within seconds warm.
log "warm-up query (full timeout)"
bash "$WQ" "warm up the embedding model" > /dev/null 2>&1 || true
export GBRAIN_QUERY_TIMEOUT=90

# Retry wrapper for PGLite lock contention with the 15-min gbrain-sync.
retry() {
  local out i
  for i in 1 2 3; do
    out=$("$@" 2>&1)
    [[ "$out" != *"Timed out waiting"* ]] && { printf '%s' "$out"; return 0; }
    sleep 60
  done
  printf '%s' "$out"; return 1
}

prev_line=$(head -1 "$STATUS" 2>/dev/null || true)
prev_fails=$(printf '%s' "$prev_line" | grep -oE 'fail:[^ ]*' | cut -d: -f2 || true)
prev_orphans=$(printf '%s' "$prev_line" | grep -oE 'orphans:[0-9]+' | grep -oE '[0-9]+' || true)

total=0; passed=0; failed_ids=(); declare -a failed_msgs=()
declare -a graph_fail_rows=()      # id<TAB>query<TAB>expect — for --build-links repair
orphan_count="${prev_orphans:-}"

while IFS=$'\t' read -r id mode query expect notes; do
  [[ -z "$id" || "$id" == \#* ]] && continue
  total=$((total+1))
  case "$mode" in
    semantic) out=$(retry bash "$WQ" "$query") || true ;;
    graph)    out=$(retry "$GBRAIN" graph-query "$query" --depth 2) || true ;;
    orphans)
      out=$("$GBRAIN" orphans 2>/dev/null | head -1)
      orphan_count=$(printf '%s' "$out" | grep -oE '^[0-9]+' || true)
      if [[ -z "$orphan_count" ]]; then
        failed_ids+=("$id"); failed_msgs+=("$id|orphan count unreadable: $out")
      elif [[ -n "$prev_orphans" ]] && (( orphan_count > prev_orphans + expect )); then
        failed_ids+=("$id"); failed_msgs+=("$id|orphans grew ${prev_orphans} -> ${orphan_count} (allowed +${expect}) — recent pages landing unlinked?")
      else
        passed=$((passed+1))
      fi
      log "$id orphans=$orphan_count (prev=${prev_orphans:-none})"
      continue ;;
    *) log "$id: unknown mode '$mode' — skipped"; total=$((total-1)); continue ;;
  esac
  hit=""
  IFS='|' read -ra alts <<< "$expect"
  for alt in "${alts[@]}"; do
    if printf '%s' "$out" | grep -qiF "$alt"; then hit="$alt"; break; fi
  done
  if [[ -n "$hit" ]]; then
    passed=$((passed+1)); log "$id PASS ($hit)"
  else
    failed_ids+=("$id"); failed_msgs+=("$id|$query — expected one of [$expect] in $mode results")
    log "$id FAIL: $query (expected: $expect)"
    [[ "$mode" == "graph" ]] && graph_fail_rows+=("${id}"$'\t'"${query}"$'\t'"${expect}")
  fi
done < "$QFILE"

# ---- Graph-connection repair (opt-in: --build-links) ------------------------
# A failing graph row usually means the relationship is declared in frontmatter
# but never became a traversable body [[wikilink]] edge. Build those edges, then
# re-test the failing rows; drop any that now traverse. Only genuinely-missing
# connections remain to be filed below.
if [[ "$BUILD_LINKS" -eq 1 && ${#graph_fail_rows[@]} -gt 0 ]]; then
  log "build-links: ${#graph_fail_rows[@]} graph row(s) failing — building entity-link edges"
  bash "$WIKI/.claude/scripts/build-graph-links.sh" --apply >> "$LOG" 2>&1 || log "warn: build-graph-links failed"
  declare -a repaired=()
  for row in "${graph_fail_rows[@]}"; do
    IFS=$'\t' read -r gid gquery gexpect <<< "$row"
    out=$(retry "$GBRAIN" graph-query "$gquery" --depth 2) || true
    IFS='|' read -ra galts <<< "$gexpect"
    for alt in "${galts[@]}"; do
      if printf '%s' "$out" | grep -qiF "$alt"; then repaired+=("$gid"); log "$gid REPAIRED (edge built)"; break; fi
    done
  done
  if (( ${#repaired[@]} > 0 )); then
    # Drop repaired ids from the failed set and credit them as passes.
    declare -a _ids=() _msgs=()
    for id in "${failed_ids[@]}"; do
      keep=1; for r in "${repaired[@]}"; do [[ "$id" == "$r" ]] && keep=0; done
      (( keep )) && _ids+=("$id")
    done
    for m in "${failed_msgs[@]}"; do
      mid="${m%%|*}"; keep=1; for r in "${repaired[@]}"; do [[ "$mid" == "$r" ]] && keep=0; done
      (( keep )) && _msgs+=("$m")
    done
    # bash 3.2: never splat a possibly-empty array under set -u — guard by count.
    if (( ${#_ids[@]} > 0 )); then failed_ids=("${_ids[@]}"); else failed_ids=(); fi
    if (( ${#_msgs[@]} > 0 )); then failed_msgs=("${_msgs[@]}"); else failed_msgs=(); fi
    passed=$((passed + ${#repaired[@]}))
    log "build-links: repaired ${#repaired[@]} graph row(s): ${repaired[*]}"
    notify "Wiki eval: auto-built ${#repaired[@]} graph connection(s) via entity-link backfill"
  fi
fi

fail_csv=$(IFS=,; echo "${failed_ids[*]:-}")
echo "pass ${passed}/${total} fail:${fail_csv:-none} orphans:${orphan_count:-unknown} $(date '+%Y-%m-%dT%H:%M:%S')" > "$STATUS"
log "result: ${passed}/${total} passed; failures: ${fail_csv:-none}"

# New failures (not failing in the previous run) feed the curation loop —
# deduped against inbox + archive, same convention as the mirror inbox drain.
new_fails=0
for msg in "${failed_msgs[@]:-}"; do
  [[ -z "$msg" ]] && continue
  id="${msg%%|*}"; body="${msg#*|}"
  [[ ",${prev_fails}," == *",${id},"* ]] && continue
  if ! grep -qsF "[eval][${id}]" "$INBOX" "$ARCHIVE"; then
    printf -- '- [eval][%s] %s (first failed %s)\n' "$id" "$body" "$(date '+%Y-%m-%d')" >> "$INBOX"
    new_fails=$((new_fails+1))
  fi
done

if (( new_fails > 0 )); then
  log "queued $new_fails new failure(s) to question inbox"
  notify "Wiki eval: $new_fails new failing question(s) — run /inbox-triage"
fi
log "=== wiki-eval run finished ==="
