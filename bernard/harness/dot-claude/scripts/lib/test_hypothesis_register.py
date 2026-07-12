#!/usr/bin/env python3
"""Edge-case tests for hypothesis_register.py."""
import os, tempfile, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "hypothesis_register.py")
fails = []


def w(p, c):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(c)


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", name, ("" if cond else f":: {detail}"))
    if not cond:
        fails.append(name)


def run(root, out, apply):
    args = [sys.executable, MOD, "--wiki-root", root, "--out", out]
    if apply:
        args.append("--apply")
    return subprocess.run(args, capture_output=True, text=True)


def main():
    root = tempfile.mkdtemp()
    try:
        h = f"{root}/wikis/health"
        # page with hypothesis (multi-line blockquote)
        w(f"{h}/wiki/synth.md",
          "---\ntype: overview\n---\n\n# Synth\n\n"
          "> Hypothesis: low ferritin contributes to fatigue\n> via reduced oxygen delivery.\n\n"
          "Some prose.\n\n> Contradiction: source A says X, source B says Y.\n")
        # page with needs-verification (no blockquote)
        w(f"{h}/shared/biomarkers/tsh.md",
          "---\ntype: biomarker\n---\n\n# TSH\n\nNeeds verification: the 2024 spike lacks a source.\n")
        # documentation line that MENTIONS the marker inside backticks — must NOT match
        w(f"{h}/wiki/doc.md",
          "---\ntype: overview\n---\n\n# Doc\n\n> Items marked `> Hypothesis:` are uncited inferences.\n")
        # raw/ page with a marker — must be EXCLUDED
        w(f"{h}/clinical/raw/2025-note.md",
          "---\ntype: record\n---\n\n# Raw\n\n> Hypothesis: radiologist speculation in source doc.\n")

        out = f"{h}/wiki/working-hypotheses.md"

        # dry-run doesn't write
        r = run(root, out, False)
        check("dry-run exits 0", r.returncode == 0, r.stderr)
        check("dry-run counts hypotheses=1", "Hypothesis=1" in r.stdout, r.stdout)
        check("dry-run counts needsverification=1", "NeedsVerification=1" in r.stdout, r.stdout)
        check("dry-run counts contradiction=1", "Contradiction=1" in r.stdout, r.stdout)
        check("dry-run creates no file", not os.path.exists(out))

        # apply
        r = run(root, out, True)
        check("apply exits 0", r.returncode == 0)
        reg = open(out).read()
        check("register created", os.path.exists(out))
        check("hypothesis text harvested", "low ferritin contributes to fatigue" in reg)
        check("multi-line continuation absorbed", "via reduced oxygen delivery" in reg)
        check("needs-verification harvested", "2024 spike lacks a source" in reg)
        check("contradiction harvested", "source A says X" in reg)
        check("backlink to source page", "[[wikis/health/wiki/synth]]" in reg)
        check("doc-line false positive EXCLUDED", "uncited inferences" not in reg)
        check("raw/ marker EXCLUDED", "radiologist speculation" not in reg)
        check("section headers present", "## Hypotheses (1)" in reg and "## Needs Verification (1)" in reg)

        # idempotent
        before = open(out).read()
        r2 = run(root, out, True)
        check("idempotent: no change on rerun", open(out).read() == before)
        check("idempotent: reports 'no change'", "no change" in r2.stdout, r2.stdout)
        check("register doesn't harvest itself", reg.count("AUTO-HYPOTHESES:START") == 1)

        # resolution lifecycle: remove the hypothesis from source -> drops off register
        w(f"{h}/wiki/synth.md", "---\ntype: overview\n---\n\n# Synth\n\nResolved now with [[cite]].\n")
        run(root, out, True)
        reg2 = open(out).read()
        check("resolved hypothesis drops off", "venous compression contributes" not in reg2)
        check("count updates to 0 hypotheses", "## Hypotheses (0)" in reg2 and "_None._" in reg2)
    finally:
        shutil.rmtree(root)
    print()
    if fails:
        print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
