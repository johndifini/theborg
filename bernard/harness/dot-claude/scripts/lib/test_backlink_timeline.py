#!/usr/bin/env python3
"""Edge-case tests for backlink_timeline.py. Builds a synthetic wiki in a temp
dir, runs the builder, and asserts behavior. Run: python3 test_backlink_timeline.py"""
import os, tempfile, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "backlink_timeline.py")
fails = []


def w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(content)


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", name, ("" if cond else f":: {detail}"))
    if not cond:
        fails.append(name)


def setup_wiki(root):
    shared = os.path.join(root, "wikis/health/shared")
    entries = os.path.join(root, "wikis/journal/wiki/entries")
    # entities
    w(f"{shared}/conditions/gerd.md", "---\ntype: condition\n---\n\n# GERD\n\nCompiled truth.\n")
    w(f"{shared}/conditions/acne.md", "---\ntype: condition\n---\n\n# ACNE\n")
    w(f"{shared}/medications/omeprazole.md", "---\ntype: medication\n---\n\n# Omeprazole\n")
    w(f"{shared}/providers/dr-x.md", "---\ntype: provider\n---\n\n# Dr X\n")
    # lonely entity — no mentions
    w(f"{shared}/biomarkers/lonely.md", "---\ntype: biomarker\n---\n\n# Lonely\n")

    # entry 1: refs gerd via frontmatter block list + dr-x via body link
    w(f"{entries}/2025-03-18-visit-a.md",
      "---\ntype: journal\nconditions:\n  - gerd\n  - nonexistent-cond\nproviders:\n  - dr-x\n---\n\n"
      "# Visit A\n\nSaw [[wikis/health/shared/providers/dr-x]] today.\n")
    # entry 2: refs gerd again (dup across entries) + acne via inline list + omeprazole via body
    w(f"{entries}/2026-01-22-visit-b.md",
      "---\ntype: journal\nconditions: [gerd, acne]\n---\n\n# Visit B\n\n"
      "On [[wikis/health/shared/medications/omeprazole|Omeprazole]] now. Also [[wikis/health/shared/conditions/gerd]].\n")
    # entry 3: no date prefix, date in frontmatter; refs acne
    w(f"{entries}/visit-c-undatedname.md",
      "---\ntype: journal\ndate_created: 2024-06-01\nconditions: [acne]\n---\n\n# Visit C\n")
    # entry 4: truly undated, refs gerd
    w(f"{entries}/visit-d.md",
      "---\ntype: journal\nconditions: [gerd]\n---\n\n# Visit D\n")
    # entry 5: references nothing
    w(f"{entries}/2025-12-01-empty.md", "---\ntype: journal\n---\n\n# Empty\n")


def run(root, apply, tl_out):
    args = [sys.executable, MOD, "--wiki-root", root, "--timeline-out", tl_out]
    if apply:
        args.append("--apply")
    return subprocess.run(args, capture_output=True, text=True)


def main():
    root = tempfile.mkdtemp()
    try:
        setup_wiki(root)
        tl_out = os.path.join(root, "wikis/health/wiki/timeline.md")

        # dry-run does not modify files
        eds_before = open(f"{root}/wikis/health/shared/conditions/gerd.md").read()
        r = run(root, False, tl_out)
        check("dry-run exits 0", r.returncode == 0, r.stderr)
        check("dry-run leaves files untouched",
              open(f"{root}/wikis/health/shared/conditions/gerd.md").read() == eds_before)
        check("dry-run does not create timeline", not os.path.exists(tl_out))

        # apply
        r = run(root, True, tl_out)
        check("apply exits 0", r.returncode == 0, r.stderr)
        gerd = open(f"{root}/wikis/health/shared/conditions/gerd.md").read()

        # gerd referenced by 3 entries (visit-a, visit-b, visit-d)
        check("gerd has Mentioned In", "## Mentioned In" in gerd)
        check("gerd links visit-a (frontmatter)", "2025-03-18-visit-a" in gerd)
        check("gerd links visit-b (body+fm)", "2026-01-22-visit-b" in gerd)
        check("gerd links visit-d (undated)", "visit-d" in gerd and "undated" in gerd)
        check("gerd dedupes visit-b (one link despite fm+body)", gerd.count("2026-01-22-visit-b") == 1,
              f"count={gerd.count('2026-01-22-visit-b')}")
        check("gerd sorted recent-first", gerd.index("2026-01-22-visit-b") < gerd.index("2025-03-18-visit-a"))
        check("no phantom link to nonexistent-cond", "nonexistent-cond" not in gerd)

        # compiled-truth zone preserved (backlinks appended after, not inside)
        check("gerd preserves compiled truth", "Compiled truth." in gerd)
        check("backlinks appended AFTER body", gerd.index("Compiled truth.") < gerd.index("## Mentioned In"))

        # provider via body link only
        drx = open(f"{root}/wikis/health/shared/providers/dr-x.md").read()
        check("dr-x backlinked via body link", "2025-03-18-visit-a" in drx)

        # omeprazole via aliased body link
        mes = open(f"{root}/wikis/health/shared/medications/omeprazole.md").read()
        check("omeprazole backlinked via aliased link", "2026-01-22-visit-b" in mes)

        # lonely entity -> no managed section at all (no mirror noise)
        lonely = open(f"{root}/wikis/health/shared/biomarkers/lonely.md").read()
        check("lonely entity gets NO Mentioned In section", "## Mentioned In" not in lonely)
        check("lonely entity untouched (no sentinels)", "AUTO-MENTIONED-IN" not in lonely)

        # timeline page
        check("timeline created", os.path.exists(tl_out))
        tl = open(tl_out).read()
        check("timeline has year headings", "### 2024" in tl and "### 2025" in tl and "### 2026" in tl)
        check("timeline chronological (2024 before 2026)", tl.index("### 2024") < tl.index("### 2026"))
        check("timeline includes fm-dated entry", "visit-c-undatedname" in tl and "2024-06-01" in tl)
        check("timeline has Undated section for visit-d", "### Undated" in tl and "visit-d" in tl)
        check("timeline shows entity refs", "[[wikis/health/shared/conditions/gerd]]" in tl)

        # idempotency: second apply changes nothing
        snap = {p: open(p).read() for p in
                [f"{root}/wikis/health/shared/conditions/gerd.md", tl_out]}
        r2 = run(root, True, tl_out)
        check("2nd apply exits 0", r2.returncode == 0)
        check("idempotent: gerd unchanged on rerun",
              open(f"{root}/wikis/health/shared/conditions/gerd.md").read() == snap[f"{root}/wikis/health/shared/conditions/gerd.md"])
        check("idempotent: timeline unchanged on rerun", open(tl_out).read() == snap[tl_out])
        check("idempotent: 0 files changed", "would change: 0" in r2.stdout or "changed: 0" in r2.stdout, r2.stdout)

        # update scenario: add a new entry, rerun -> gerd picks it up, no duplicate section
        w(f"{root}/wikis/journal/wiki/entries/2026-06-01-visit-e.md",
          "---\ntype: journal\nconditions: [gerd]\n---\n\n# Visit E\n")
        run(root, True, tl_out)
        eds2 = open(f"{root}/wikis/health/shared/conditions/gerd.md").read()
        check("update: new entry appears", "2026-06-01-visit-e" in eds2)
        check("update: still exactly one Mentioned In section", eds2.count("## Mentioned In") == 1)
        check("update: still one START sentinel", eds2.count("AUTO-MENTIONED-IN:START") == 1)

        # removal scenario: delete every entry referencing acne, rerun -> section removed
        os.remove(f"{root}/wikis/journal/wiki/entries/2026-01-22-visit-b.md")
        os.remove(f"{root}/wikis/journal/wiki/entries/visit-c-undatedname.md")
        acne_before = open(f"{root}/wikis/health/shared/conditions/acne.md").read()
        check("removal precondition: acne had a section", "## Mentioned In" in acne_before)
        run(root, True, tl_out)
        acne_after = open(f"{root}/wikis/health/shared/conditions/acne.md").read()
        check("removal: stale section cleaned up", "## Mentioned In" not in acne_after)
        check("removal: no orphaned sentinels", "AUTO-MENTIONED-IN" not in acne_after)
        check("removal: page body preserved", "# ACNE" in acne_after)
    finally:
        shutil.rmtree(root)

    print()
    if fails:
        print(f"{len(fails)} FAILED: {fails}")
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
