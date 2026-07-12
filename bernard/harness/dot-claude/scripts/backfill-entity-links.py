#!/usr/bin/env python3
"""
Backfill inline [[wikilinks]] from frontmatter providers/conditions/medications
into body text so GBrain graph-query can traverse them.

Adds an ## Entity Links section at the end of each qualifying file.
Safe to re-run: skips files that already have the section.

Usage:
  python3 backfill-entity-links.py          # dry run (no writes)
  python3 backfill-entity-links.py --apply  # write changes
"""

import re
import sys
from pathlib import Path

WIKI_ROOT = Path("/Users/lashawsalta/life-wiki/wikis")

ENTITY_FIELDS = {
    "providers": "wikis/health/shared/providers",
    "conditions": "wikis/health/shared/conditions",
    "medications": "wikis/health/shared/medications",
}

APPLY = "--apply" in sys.argv


def extract_frontmatter(text):
    """Return (fm_text, body) or (None, text) if no frontmatter."""
    if not text.startswith("---\n"):
        return None, text
    close = text.find("\n---\n", 4)
    if close == -1:
        return None, text
    return text[4:close], text[close + 5:]


def parse_list_field(fm_text, field):
    """Parse 'field: [a, b, c]' or 'field: []' from frontmatter."""
    m = re.search(rf"^{field}:\s*\[([^\]]*)\]", fm_text, re.MULTILINE)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def build_entity_links_section(fm_text):
    """Build the ## Entity Links section text, or None if nothing to add."""
    lines = []
    for field, base_path in ENTITY_FIELDS.items():
        slugs = parse_list_field(fm_text, field)
        if not slugs:
            continue
        label = field.capitalize()
        links = " · ".join(f"[[{base_path}/{s}]]" for s in slugs)
        lines.append(f"**{label}:** {links}")
    if not lines:
        return None
    return "\n## Entity Links\n\n" + "\n\n".join(lines) + "\n"


def process_file(path):
    text = path.read_text(encoding="utf-8")
    fm_text, body = extract_frontmatter(text)

    if fm_text is None:
        return "skip", "no frontmatter"

    if "## Entity Links" in text:
        return "skip", "already has entity links"

    section = build_entity_links_section(fm_text)
    if section is None:
        return "skip", "no non-empty entity fields"

    if APPLY:
        new_text = text.rstrip("\n") + "\n" + section
        path.write_text(new_text, encoding="utf-8")
        return "updated", section.strip()

    return "would update", section.strip()


def main():
    updated, skipped_empty, skipped_exists, skipped_nofm = [], [], [], []

    for md_file in sorted(WIKI_ROOT.rglob("*.md")):
        status, detail = process_file(md_file)
        rel = str(md_file.relative_to(WIKI_ROOT.parent))

        if status in ("updated", "would update"):
            updated.append((rel, detail))
        elif "already" in detail:
            skipped_exists.append(rel)
        elif "no frontmatter" in detail:
            skipped_nofm.append(rel)
        else:
            skipped_empty.append(rel)

    mode = "APPLY" if APPLY else "DRY RUN"
    print(f"\n=== {mode} ===")
    print(f"\nFiles to modify: {len(updated)}")
    for rel, section in updated:
        print(f"\n  + {rel}")
        for line in section.splitlines():
            print(f"      {line}")

    print(f"\nSkipped (already have entity links): {len(skipped_exists)}")
    print(f"Skipped (no entity fields):          {len(skipped_empty)}")
    print(f"Skipped (no frontmatter):            {len(skipped_nofm)}")

    if not APPLY:
        print("\nRun with --apply to write changes.")


if __name__ == "__main__":
    main()
