#!/usr/bin/env python3
"""Edge-case tests for self_interrogate.py."""
import os, tempfile, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "self_interrogate.py")
fails = []


def w(p, c):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(c)


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", name, ("" if cond else f":: {detail}"))
    if not cond:
        fails.append(name)


def run(root):
    return subprocess.run([sys.executable, MOD, "--wiki-root", root, "--today", "2026-06-14"],
                          capture_output=True, text=True)


def main():
    root = tempfile.mkdtemp()
    try:
        shared = f"{root}/wikis/health/shared"
        entries = f"{root}/wikis/journal/wiki/entries"
        # connected condition (links to a med) — should NOT be flagged isolated
        w(f"{shared}/conditions/acne.md", "---\ntype: condition\n---\n\n# ACNE\n\nTreated with [[wikis/health/shared/medications/omeprazole]].\n")
        w(f"{shared}/medications/omeprazole.md", "---\ntype: medication\n---\n\n# Omeprazole\n")
        # isolated condition — flagged D1
        w(f"{shared}/conditions/orphan-cond.md", "---\ntype: condition\n---\n\n# Orphan Cond\n")
        # untreated med — flagged D2
        w(f"{shared}/medications/mystery-drug.md", "---\ntype: medication\n---\n\n# Mystery Drug\n")
        # entries: one references a missing med slug (D3), dates create a gap (D5)
        w(f"{entries}/2026-01-01-a.md", "---\ntype: journal\nmedications: [ghost-med, omeprazole]\n---\n\n# A\n")
        w(f"{entries}/2026-06-01-b.md", "---\ntype: journal\nconditions: [acne]\n---\n\n# B\n")

        r = run(root)
        out = r.stdout
        check("exits 0", r.returncode == 0, r.stderr)
        check("D1 flags isolated condition", "orphan-cond" in out and "isolated" in out)
        check("D1 does NOT flag connected acne", "'acne'" not in out, out)
        check("D2 flags untreated mystery-drug", "mystery-drug" in out)
        check("D2 does NOT flag omeprazole (referenced by acne+entry)", "'omeprazole'" not in out, out)
        check("D3 flags missing entity ghost-med", "ghost-med" in out and "no page exists" in out)
        check("D3 count reflected", "1 entry frontmatter" in out, out)
        check("D5 flags Jan->Jun gap", "timeline complete between 2026-01-01 and 2026-06-01" in out)
        check("all lines tagged [self-interrogate]",
              all("[self-interrogate]" in ln for ln in out.strip().splitlines() if ln.strip()))
        check("lines carry --today date", all(ln.startswith("- 2026-06-14") for ln in out.strip().splitlines() if ln.strip()))

        # no-gap scenario: empty wiki -> no output, exit 0
        empty = tempfile.mkdtemp()
        os.makedirs(f"{empty}/wikis/health/shared/conditions")
        os.makedirs(f"{empty}/wikis/journal/wiki/entries")
        r2 = subprocess.run([sys.executable, MOD, "--wiki-root", empty, "--today", "2026-06-14"],
                            capture_output=True, text=True)
        check("empty wiki exits 0", r2.returncode == 0)
        check("empty wiki emits nothing", r2.stdout.strip() == "", repr(r2.stdout))
        shutil.rmtree(empty)

        # bad root -> exit 2
        r3 = subprocess.run([sys.executable, MOD, "--wiki-root", "/no/such/dir", "--today", "x"],
                            capture_output=True, text=True)
        check("bad root exits 2", r3.returncode == 2)
    finally:
        shutil.rmtree(root)
    print()
    if fails:
        print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
