#!/usr/bin/env bash
# wiki-lint-structural.sh
# Machine-runnable structural checks for life-wiki.
# Any agent or cron job can call this — no Claude Code runtime required.
# Semantic checks (injection rescan, contradiction detection, citation adequacy)
# remain in the /wiki-lint Claude skill and require a model session.
#
# Severity contract:
#   CRITICAL — breaks the wiki's auditability or graph integrity; fix before any ingest.
#              Includes broken citations to entity pages (providers/conditions/
#              medications/biomarkers/people): a citation pointing nowhere violates
#              the core promise that every claim is traceable.
#   WARNING  — drift from the page contract; fix opportunistically.
#
# Outputs a "Summary: X critical, Y warnings, Z info" line last.
# Exit code is always 0 — caller parses the Summary line for gating.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WIKI_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
WIKIS_DIR="$WIKI_DIR/wikis"
INGEST_DIR="$WIKI_DIR/ingest"
HANDOFF_FILE="$WIKI_DIR/AGENT-HANDOFF.md"
SOURCES_FILE="$WIKIS_DIR/sources.md"

critical=0
warnings=0
info=0

_critical() { printf 'CRITICAL  %s\n' "$1"; critical=$(( critical + 1 )); }
_warning()  { printf 'WARNING   %s\n' "$1"; warnings=$(( warnings + 1 )); }
_info()     { printf 'INFO      %s\n' "$1"; info=$(( info + 1 )); }

# Extract the frontmatter block (between the first two --- lines) of a file.
_frontmatter() { awk 'NR==1{next} /^---[[:space:]]*$/{exit} {print}' "$1"; }

printf 'WIKI LINT STRUCTURAL — %s\n' "$(date '+%Y-%m-%d')"
printf '================================================\n\n'

# ── 1. AGENT-HANDOFF.md exists and is reasonably fresh ───────────────────────
if [ ! -f "$HANDOFF_FILE" ]; then
    _critical "AGENT-HANDOFF.md does not exist — create it so agents can orient without re-reading everything."
else
    HANDOFF_MOD=$(stat -f '%m' "$HANDOFF_FILE" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE_DAYS=$(( (NOW - HANDOFF_MOD) / 86400 ))
    if [ "$AGE_DAYS" -gt 14 ]; then
        _warning "AGENT-HANDOFF.md is ${AGE_DAYS} days old — update before next multi-agent session."
    fi
fi

# ── 2. sources.md has at least one registered source ────────────────────────
if [ -f "$SOURCES_FILE" ]; then
    # Count pipe-delimited rows; subtract 2 for the header and separator rows
    PIPE_ROWS=$(grep -c '^|' "$SOURCES_FILE" 2>/dev/null || echo "0")
    DATA_ROWS=$(( PIPE_ROWS - 2 ))
    if [ "$DATA_ROWS" -le 0 ]; then
        _warning "wikis/sources.md has no registered sources — update after every ingest."
    fi
else
    _critical "wikis/sources.md is missing."
fi

# ── 3. Required sub-wiki log.md files exist ───────────────────────────────────
REQUIRED_LOGS=(
    "wikis/health/clinical/wiki/log.md"
    "wikis/health/research/wiki/log.md"
    "wikis/health/personal-tracking/wiki/log.md"
    "wikis/journal/wiki/log.md"
)
for LOG_PATH in "${REQUIRED_LOGS[@]}"; do
    if [ ! -f "$WIKI_DIR/$LOG_PATH" ]; then
        _critical "Missing required log file: $LOG_PATH"
    fi
done

# ── 4. Frontmatter present on leaf wiki pages ─────────────────────────────────
# Meta files (index, log, sources, tags, graph-rules, overview, schema) are exempt.
EXEMPT_PATTERN="(index|log|sources|tags|graph-rules|overview|sidecar-schema|queue)\.md$"
MISSING_FM=0
while IFS= read -r -d '' mdfile; do
    REL="${mdfile#$WIKI_DIR/}"
    if echo "$REL" | grep -qE "$EXEMPT_PATTERN"; then
        continue
    fi
    FIRST_LINE=$(head -1 "$mdfile" 2>/dev/null || true)
    if [ "$FIRST_LINE" != "---" ]; then
        _warning "Missing frontmatter: $REL"
        MISSING_FM=$(( MISSING_FM + 1 ))
    fi
done < <(find "$WIKIS_DIR" -name "*.md" -print0 2>/dev/null)

if [ "$MISSING_FM" -gt 3 ]; then
    _info "$MISSING_FM pages missing frontmatter — run /lint for the full list."
fi

# ── 4b. Broken wikilinks (Obsidian-style, no .md extension) ─────────────────
# Broken links to ENTITY pages are CRITICAL: entity pages are the graph, and a
# citation pointing at a nonexistent entity breaks both auditability and GBrain
# traversal. Other broken links (records, transcripts, drafts) are warnings.
BROKEN_LINKS=0
BROKEN_ENTITY=0
while IFS= read -r link; do
    target="${link%%#*}"                 # strip anchor
    # Obsidian links omit .md — try with and without
    if [ ! -f "$WIKI_DIR/$target" ] && [ ! -f "$WIKI_DIR/${target}.md" ]; then
        case "$target" in
            wikis/health/shared/providers/*|wikis/health/shared/conditions/*|\
            wikis/health/shared/medications/*|wikis/health/shared/biomarkers/*|\
            wikis/shared/people/*)
                _critical "Broken entity citation: [[${link}]] — create the entity page (status: staged is fine) or fix the slug."
                BROKEN_ENTITY=$(( BROKEN_ENTITY + 1 ))
                ;;
            *)
                _warning "Broken wikilink: [[${link}]]"
                BROKEN_LINKS=$(( BROKEN_LINKS + 1 ))
                ;;
        esac
    fi
done < <(grep -roh '\[\[wikis/[^]|]*\]\]' "$WIKIS_DIR" 2>/dev/null \
    | sed 's/\[\[//;s/\]\]//' | sort -u)

# ── 4c. Entity pages missing ## Entity Links section ────────────────────────
# Every page with type: condition|medication|provider|biomarker must have a
# ## Entity Links section — otherwise GBrain graph traversal is broken for it.
ENTITY_TYPES="condition|medication|provider|biomarker"
MISSING_EL=0
while IFS= read -r -d '' mdfile; do
    REL="${mdfile#$WIKI_DIR/}"
    # Only check pages in shared/ or providers/ entity directories
    case "$REL" in
        wikis/health/shared/conditions/*|wikis/health/shared/medications/*|\
        wikis/health/shared/providers/*|wikis/health/shared/biomarkers/*) ;;
        *) continue ;;
    esac
    # Check frontmatter type matches entity types
    TYPE_LINE=$(head -20 "$mdfile" | grep '^type:' | head -1)
    if ! echo "$TYPE_LINE" | grep -qE "($ENTITY_TYPES)"; then
        continue
    fi
    if ! grep -q '## Entity Links' "$mdfile"; then
        _warning "Entity page missing ## Entity Links: $REL"
        MISSING_EL=$(( MISSING_EL + 1 ))
    fi
done < <(find "$WIKIS_DIR" -name "*.md" -print0 2>/dev/null)
if [ "$MISSING_EL" -gt 3 ]; then
    _info "$MISSING_EL entity pages missing ## Entity Links — add before ingest completes."
fi

# ── 4d. Page contract: required frontmatter fields + valid status ─────────────
# Applies to non-raw wiki pages (raw/ files are source mirrors, not wiki pages).
# Required: type, status, domain, source_paths, confidence, tags, date_created,
# and date_updated OR date_last_updated.
FIELD_FAILS=0
STATUS_FAILS=0
# ── 4e. Journal/recording entries: structured entity fields ──────────────────
# Contract (CLAUDE.md "Page frontmatter standard"): journal and recording entries
# carry providers/conditions/medications lists; empty list = explicitly none.
# Pure personal entries (no entity keys AND no body entity links) are exempt.
# A non-empty entity list requires a ## Entity Links section in the body —
# frontmatter alone creates no graph edges.
# Fix drift mechanically: python3 .claude/scripts/backfill-entity-frontmatter.py --apply
# then python3 .claude/scripts/backfill-entity-links.py --apply
ENTRY_KEY_FAILS=0
ENTRY_EL_FAILS=0
while IFS= read -r -d '' mdfile; do
    REL="${mdfile#$WIKI_DIR/}"
    echo "$REL" | grep -qE "$EXEMPT_PATTERN" && continue
    [ "$(head -1 "$mdfile" 2>/dev/null)" = "---" ] || continue
    FM=$(_frontmatter "$mdfile")

    # 4d: required fields
    MISSING_KEYS=""
    for key in type status domain source_paths confidence tags date_created; do
        echo "$FM" | grep -q "^${key}:" || MISSING_KEYS="$MISSING_KEYS $key"
    done
    echo "$FM" | grep -qE '^date_(last_)?updated:' || MISSING_KEYS="$MISSING_KEYS date_updated"
    if [ -n "$MISSING_KEYS" ]; then
        FIELD_FAILS=$(( FIELD_FAILS + 1 ))
        [ "$FIELD_FAILS" -le 15 ] && _warning "Missing required frontmatter fields (${MISSING_KEYS# }): $REL"
    fi

    # 4d: status must be staged|active|archived
    STATUS_LINE=$(echo "$FM" | grep '^status:' | head -1)
    if [ -n "$STATUS_LINE" ] && ! echo "$STATUS_LINE" | grep -qE '^status:[[:space:]]*(staged|active|archived)[[:space:]]*$'; then
        STATUS_FAILS=$(( STATUS_FAILS + 1 ))
        [ "$STATUS_FAILS" -le 15 ] && _warning "Invalid status value (${STATUS_LINE}): $REL"
    fi

    # 4e: journal/recording entity-field contract
    TYPE_LINE=$(echo "$FM" | grep '^type:' | head -1)
    if echo "$TYPE_LINE" | grep -qE '^type:[[:space:]]*(journal|recording)'; then
        HAS_ALL_KEYS=1
        HAS_SOME_KEY=0
        for key in providers conditions medications; do
            if echo "$FM" | grep -q "^${key}:"; then
                HAS_SOME_KEY=1
            else
                HAS_ALL_KEYS=0
            fi
        done
        HAS_BODY_LINK=0
        grep -qE '\[\[wikis/health/shared/(providers|conditions|medications)/' "$mdfile" && HAS_BODY_LINK=1
        if [ "$HAS_ALL_KEYS" -eq 0 ] && { [ "$HAS_SOME_KEY" -eq 1 ] || [ "$HAS_BODY_LINK" -eq 1 ]; }; then
            ENTRY_KEY_FAILS=$(( ENTRY_KEY_FAILS + 1 ))
            [ "$ENTRY_KEY_FAILS" -le 15 ] && _warning "Entry missing providers/conditions/medications frontmatter: $REL"
        fi
        # Non-empty entity list requires a body ## Entity Links section
        if echo "$FM" | grep -qE '^(providers|conditions|medications):[[:space:]]*\[[^]]' ; then
            if ! grep -q '## Entity Links' "$mdfile"; then
                ENTRY_EL_FAILS=$(( ENTRY_EL_FAILS + 1 ))
                [ "$ENTRY_EL_FAILS" -le 15 ] && _warning "Entry has entity frontmatter but no ## Entity Links section: $REL"
            fi
        fi
    fi
done < <(find "$WIKIS_DIR" -name "*.md" -not -path "*/raw/*" -print0 2>/dev/null)
[ "$FIELD_FAILS" -gt 15 ] && _warning "...and $(( FIELD_FAILS - 15 )) more pages missing required frontmatter fields."
[ "$STATUS_FAILS" -gt 15 ] && _warning "...and $(( STATUS_FAILS - 15 )) more pages with invalid status."
[ "$ENTRY_KEY_FAILS" -gt 15 ] && _warning "...and $(( ENTRY_KEY_FAILS - 15 )) more entries missing entity frontmatter (run backfill-entity-frontmatter.py)."
[ "$ENTRY_EL_FAILS" -gt 15 ] && _warning "...and $(( ENTRY_EL_FAILS - 15 )) more entries missing ## Entity Links (run backfill-entity-links.py)."

# ── 4f. Every raw source file is registered in sources.md ─────────────────────
# Matches by basename so both per-file rows and batch rows (IDs listed in the
# Primary Pages column) count as registered. Aggregated per raw directory.
if [ -f "$SOURCES_FILE" ]; then
    while IFS= read -r -d '' rawdir; do
        UNREG=0
        EXAMPLES=""
        while IFS= read -r -d '' rawfile; do
            base="$(basename "$rawfile" .md)"
            if ! grep -qF "$base" "$SOURCES_FILE"; then
                UNREG=$(( UNREG + 1 ))
                [ "$UNREG" -le 3 ] && EXAMPLES="$EXAMPLES ${rawfile#$WIKI_DIR/}"
            fi
        done < <(find "$rawdir" -name '*.md' -print0 2>/dev/null)
        if [ "$UNREG" -gt 0 ]; then
            _warning "$UNREG raw file(s) under ${rawdir#$WIKI_DIR/}/ not registered in wikis/sources.md (e.g.${EXAMPLES})"
        fi
    done < <(find "$WIKIS_DIR" -type d -name raw -print0 2>/dev/null)
fi

# ── 5. No audio binaries in git-tracked paths ────────────────────────────────
AUDIO_COUNT=0
while IFS= read -r -d '' afile; do
    _critical "Audio binary in git-tracked path: ${afile#$WIKI_DIR/}"
    AUDIO_COUNT=$(( AUDIO_COUNT + 1 ))
done < <(find "$WIKIS_DIR" \( \
    -name "*.m4a" -o -name "*.mp3" -o -name "*.wav" \
    -o -name "*.mp4" -o -name "*.aac" \
    \) -print0 2>/dev/null)

# ── 6. Every ingest file in pipeline subdirs has a .meta.json sidecar ────────
PIPELINE_DIRS=(voice-memos email secure web biometric location finance ai-chats)
for PIPELINE in "${PIPELINE_DIRS[@]}"; do
    PIPE_PATH="$INGEST_DIR/$PIPELINE"
    [ -d "$PIPE_PATH" ] || continue
    while IFS= read -r -d '' mdfile; do
        SIDECAR="${mdfile%.md}.meta.json"
        if [ ! -f "$SIDECAR" ]; then
            _warning "No .meta.json sidecar: ${mdfile#$WIKI_DIR/}"
        fi
    done < <(find "$PIPE_PATH" -maxdepth 1 -name "*.md" \
        ! -name "smoketest*" ! -name "queue*" -print0 2>/dev/null)
done

# ── 7. No raw source files hand-edited (detect uncommitted changes in raw/) ──
if command -v git &>/dev/null; then
    RAW_DIRTY=$(git -C "$WIKI_DIR" diff --name-only HEAD 2>/dev/null \
        | grep '/raw/' || true)
    if [ -n "$RAW_DIRTY" ]; then
        _critical "Uncommitted edits in raw/ folders — raw sources must not be hand-edited:"
        printf '          %s\n' "$RAW_DIRTY"
    fi
fi

# ── 8. Agent instruction files: line count ≤ 200, symlinks intact ────────────
AGENT_MAX=200
# Check all non-symlink agent instruction files for line count
while IFS= read -r -d '' agent_file; do
    LINE_COUNT=$(wc -l < "$agent_file")
    if [ "$LINE_COUNT" -gt "$AGENT_MAX" ]; then
        _critical "Agent file exceeds ${AGENT_MAX}-line limit: ${agent_file#$WIKI_DIR/} (${LINE_COUNT} lines) — move reference content to .claude/reference/"
    fi
done < <(find "$WIKI_DIR" -maxdepth 3 \
    \( -name "CLAUDE.md" -o -name "AGENTS.md" -o -name "GEMINI.md" \) \
    -not -type l -print0 2>/dev/null)

# AGENTS.md and GEMINI.md must be symlinks to CLAUDE.md, not standalone copies
for AGENT_ALIAS in AGENTS.md GEMINI.md; do
    ALIAS_PATH="$WIKI_DIR/$AGENT_ALIAS"
    if [ -e "$ALIAS_PATH" ] && [ ! -L "$ALIAS_PATH" ]; then
        _critical "$AGENT_ALIAS is a standalone file, not a symlink to CLAUDE.md — run: ln -sf CLAUDE.md $AGENT_ALIAS"
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
printf '\n'
printf 'Summary: %d critical, %d warnings, %d info\n' \
    "$critical" "$warnings" "$info"
