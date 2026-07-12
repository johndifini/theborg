#!/usr/bin/env python3
"""
Inverse of backfill-entity-links.py: derive frontmatter providers/conditions/medications
lists from entity wikilinks already present in the page body.

Body wikilinks are the source of truth (they create GBrain graph edges); the frontmatter
lists are derived metadata for entity resolution. This script closes the drift where an
entry links entities in the body but lacks the structured frontmatter fields.

Only adds keys that are missing — never rewrites an existing list. Slugs that do not
correspond to an actual entity page file are reported and skipped, never written.

Usage:
  python3 backfill-entity-frontmatter.py          # dry run (no writes)
  python3 backfill-entity-frontmatter.py --apply  # write changes
"""

import re
import sys
from pathlib import Path

WIKI_ROOT = Path("/Users/lashawsalta/life-wiki/wikis")
ENTRY_DIRS = [
    WIKI_ROOT / "journal" / "wiki" / "entries",
    WIKI_ROOT / "health" / "clinical" / "wiki" / "appointments",
]

ENTITY_FIELDS = {
    "providers": WIKI_ROOT / "health" / "shared" / "providers",
    "conditions": WIKI_ROOT / "health" / "shared" / "conditions",
    "medications": WIKI_ROOT / "health" / "shared" / "medications",
}

LINK_RE = re.compile(
    r"\[\[wikis/health/shared/(providers|conditions|medications)/([a-z0-9-]+)"
)

APPLY = "--apply" in sys.argv


def split_frontmatter(text):
    """Return (fm_lines, body, has_fm)."""
    if not text.startswith("---\n"):
        return None, text, False
    close = text.find("\n---\n", 4)
    if close == -1:
        return None, text, False
    return text[4:close], text[close + 5:], True


def main():
    changed = 0
    skipped_bad_slugs = []
    entry_files = [f for d in ENTRY_DIRS for f in sorted(d.glob("*.md"))]
    for mdfile in entry_files:
        text = mdfile.read_text(encoding="utf-8")
        fm, body, has_fm = split_frontmatter(text)
        if not has_fm:
            continue

        missing = [f for f in ENTITY_FIELDS
                   if not re.search(rf"^{f}:", fm, re.MULTILINE)]
        if not missing:
            continue

        found = {f: [] for f in ENTITY_FIELDS}
        for kind, slug in LINK_RE.findall(body):
            if slug in found[kind]:
                continue
            if not (ENTITY_FIELDS[kind] / f"{slug}.md").exists():
                skipped_bad_slugs.append(f"{mdfile.name}: {kind}/{slug}")
                continue
            found[kind].append(slug)

        # Pure personal entries (no entity keys, no body entity links) are exempt
        # from the structured-field requirement. Anything already participating in
        # the entity system gets all three keys — empty list means "none mentioned".
        has_any_key = len(missing) < len(ENTITY_FIELDS)
        has_any_link = any(found.values())
        if not has_any_key and not has_any_link:
            continue

        new_lines = [f"{f}: [{', '.join(found[f])}]" for f in missing]
        new_fm = fm + "\n" + "\n".join(new_lines)
        new_text = f"---\n{new_fm}\n---\n{body}"

        rel = mdfile.relative_to(WIKI_ROOT.parent)
        print(f"{'WRITE' if APPLY else 'DRY  '} {rel}: add {', '.join(new_lines)}")
        if APPLY:
            mdfile.write_text(new_text, encoding="utf-8")
        changed += 1

    print(f"\n{changed} entries {'updated' if APPLY else 'would be updated'}")
    if skipped_bad_slugs:
        print(f"\n{len(skipped_bad_slugs)} body links point at nonexistent entity pages "
              f"(NOT written to frontmatter):")
        for s in skipped_bad_slugs:
            print(f"  {s}")


if __name__ == "__main__":
    main()
