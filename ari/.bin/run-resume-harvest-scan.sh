#!/bin/bash
# Model-less weekly detector for private resume artifacts that need harvesting.
# The tracked script contains only method; all candidate-specific data is read
# at runtime from Ari's gitignored .private directory.
set -euo pipefail

case "${1:-}" in
  "") DRY_RUN=0 ;;
  --dry-run) DRY_RUN=1 ;;
  *) echo "usage: $(basename "$0") [--dry-run]" >&2; exit 64 ;;
esac

BORG_ROOT_DIR="${BORG_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ARI_DIR="$BORG_ROOT_DIR/ari"
SCANNER="$ARI_DIR/.bin/resume_corpus.py"
RESUME_DIR="$ARI_DIR/.private/Resumes"
MANIFEST="$ARI_DIR/.private/Resume Corpus Manifest.json"
REPORT_FILE="$(mktemp "${TMPDIR:-/tmp}/resume-harvest-report.XXXXXX")"
trap 'rm -f "$REPORT_FILE"' EXIT

python3 "$SCANNER" scan \
  --resume-dir "$RESUME_DIR" \
  --manifest "$MANIFEST" \
  --minimum-age-hours 48 > "$REPORT_FILE"

[[ -s "$REPORT_FILE" ]] || exit 0

if (( DRY_RUN == 1 )); then
  cat "$REPORT_FILE"
else
  "$BORG_ROOT_DIR/.bin/notify-email.sh" ari "Pending resume harvest" < "$REPORT_FILE"
fi
