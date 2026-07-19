#!/usr/bin/env bash
# Expose Borg Claude Code commands to Codex's deprecated custom-prompt surface.
# .claude/commands/*.md remains canonical; Codex receives exact symlinks.
set -euo pipefail

MODE="sync"
case "${1:-}" in
  --check) MODE="check" ;;
  --print) MODE="print" ;;
  "") ;;
  *) echo "usage: $(basename "$0") [--check|--print]" >&2; exit 64 ;;
esac

BORG_ROOT="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
PROMPTS_DIR="${BORG_CODEX_PROMPTS_DIR:-$CODEX_ROOT/prompts}"
MANIFEST="$PROMPTS_DIR/.theborg-managed-prompts.tsv"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/theborg-prompts.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

INVENTORY="$WORK_DIR/inventory.tsv"
PLAN="$WORK_DIR/plan.tsv"
: > "$INVENTORY"
: > "$PLAN"

while IFS= read -r source; do
  rel="${source#"$BORG_ROOT"/}"
  case "$rel" in
    .claude/commands/*) scope="workspace" ;;
    */.claude/commands/*) scope="${rel%%/.claude/commands/*}" ;;
    *) continue ;;
  esac

  name="$(basename "$source" .md)"
  case "$name" in
    ""|*[!A-Za-z0-9._-]*)
      echo "unsupported command filename: $source" >&2
      exit 1
      ;;
  esac
  safe_scope="$(printf '%s' "$scope" | tr '/ _' '---' | tr -cd 'A-Za-z0-9.-')"
  printf '%s\t%s\t%s\n' "$name" "$safe_scope" "$source" >> "$INVENTORY"
done < <(
  find "$BORG_ROOT" \
    \( -path "$BORG_ROOT/.git" -o -path "$BORG_ROOT/bernard" \
       -o -path '*/.git' -o -path '*/node_modules' -o -path '*/dist' -o -path '*/build' \) -prune \
    -o -type f -path '*/.claude/commands/*.md' -print | LC_ALL=C sort
)

while IFS=$'\t' read -r name scope source; do
  count="$(awk -F '\t' -v wanted="$name" '$1 == wanted { count++ } END { print count + 0 }' "$INVENTORY")"
  if (( count > 1 )); then
    link_name="$scope-$name"
  else
    link_name="$name"
  fi
  printf '%s\t%s\n' "$link_name" "$source" >> "$PLAN"
done < "$INVENTORY"

LC_ALL=C sort -o "$PLAN" "$PLAN"
duplicates="$(cut -f1 "$PLAN" | uniq -d)"
if [[ -n "$duplicates" ]]; then
  echo "command names still collide after scope-prefixing:" >&2
  echo "$duplicates" >&2
  exit 1
fi

if [[ "$MODE" == "print" ]]; then
  while IFS=$'\t' read -r link_name source; do
    printf '/prompts:%-28s %s\n' "$link_name" "${source#"$BORG_ROOT"/}"
  done < "$PLAN"
  exit 0
fi

managed_target() {
  local link_name="$1"
  [[ -f "$MANIFEST" ]] || return 1
  awk -F '\t' -v wanted="$link_name" '$1 == wanted { print $2; found=1; exit } END { if (!found) exit 1 }' "$MANIFEST"
}

errors=0
while IFS=$'\t' read -r link_name source; do
  dest="$PROMPTS_DIR/$link_name.md"
  if [[ -L "$dest" ]]; then
    current="$(readlink "$dest")"
    if [[ "$current" == "$source" ]]; then
      continue
    fi
    old="$(managed_target "$link_name" 2>/dev/null || true)"
    if [[ "$current" == "$old" && -n "$old" && "$MODE" == "sync" ]]; then
      continue
    fi
    echo "conflict: $dest points to $current" >&2
    errors=$((errors + 1))
  elif [[ -e "$dest" ]]; then
    echo "conflict: $dest exists and is not a managed symlink" >&2
    errors=$((errors + 1))
  else
    if [[ "$MODE" != "sync" ]]; then
      echo "missing: $dest -> $source" >&2
      errors=$((errors + 1))
    fi
  fi
done < "$PLAN"

if [[ -f "$MANIFEST" ]]; then
  while IFS=$'\t' read -r old_name old_source; do
    if ! awk -F '\t' -v wanted="$old_name" '$1 == wanted { found=1 } END { exit !found }' "$PLAN"; then
      dest="$PROMPTS_DIR/$old_name.md"
      if [[ -L "$dest" && "$(readlink "$dest")" == "$old_source" ]]; then
        if [[ "$MODE" == "sync" ]]; then
          continue
        fi
        echo "stale: $dest -> $old_source" >&2
        errors=$((errors + 1))
      elif [[ -e "$dest" || -L "$dest" ]]; then
        echo "stale manifest entry is no longer safely managed: $dest" >&2
        errors=$((errors + 1))
      fi
    fi
  done < "$MANIFEST"
fi

(( errors == 0 )) || exit 1
[[ "$MODE" == "check" ]] && { echo "Codex prompt bridge is current ($(wc -l < "$PLAN" | tr -d ' ') commands)."; exit 0; }

mkdir -p "$PROMPTS_DIR"

if [[ -f "$MANIFEST" ]]; then
  while IFS=$'\t' read -r old_name old_source; do
    if ! awk -F '\t' -v wanted="$old_name" '$1 == wanted { found=1 } END { exit !found }' "$PLAN"; then
      dest="$PROMPTS_DIR/$old_name.md"
      if [[ -L "$dest" && "$(readlink "$dest")" == "$old_source" ]]; then
        rm "$dest"
      fi
    fi
  done < "$MANIFEST"
fi

while IFS=$'\t' read -r link_name source; do
  ln -sfn "$source" "$PROMPTS_DIR/$link_name.md"
done < "$PLAN"

cp "$PLAN" "$MANIFEST.tmp"
mv "$MANIFEST.tmp" "$MANIFEST"
echo "Synced $(wc -l < "$PLAN" | tr -d ' ') Borg commands into $PROMPTS_DIR. Restart Codex to reload them."
