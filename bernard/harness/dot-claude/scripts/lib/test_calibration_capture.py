#!/usr/bin/env python3
"""Edge-case tests for calibration_capture.py."""
import os, tempfile, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "calibration_capture.py")
fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "-", name, ("" if cond else f":: {detail}"))
    if not cond:
        fails.append(name)


def run(archive, out=""):
    args = [sys.executable, MOD, "--archive", archive]
    if out:
        args += ["--out-tsv", out, "--apply"]
    return subprocess.run(args, capture_output=True, text=True)


def main():
    d = tempfile.mkdtemp()
    try:
        arc = f"{d}/archive.md"
        open(arc, "w").write("""# Archive

- 2026-06-01 — Is the timeline complete between 2026-01-01 and 2026-03-01? — gap [self-interrogate] [dismissed 2026-06-02: known life gap]
- 2026-06-01 — Is the timeline complete between 2026-04-01 and 2026-05-20? — gap [self-interrogate] [dismissed 2026-06-02: normal]
- 2026-06-01 — Is the timeline complete between 2026-02-01 and 2026-03-25? — gap [self-interrogate] [dismissed 2026-06-02: normal]
- 2026-06-01 — Is the timeline complete between 2026-01-10 and 2026-03-02? — gap [self-interrogate] [dismissed 2026-06-02: normal]
- 2026-05-01 — Should there be an entity page for 'foo'? — missing [self-interrogate] [done 2026-05-04 → wikis/health/shared/medications/foo]
- 2026-05-20 — Cross-model divergence: claim X — Claude=SUPPORTED, Codex=UNSUPPORTED [cross-model] [done 2026-05-22 → wikis/x]
- 2026-05-20 — a question with no outcome yet [self-interrogate]
- 2026-05-20 — a plain manual gap — missing [done 2026-05-21 → wikis/y]
""")
        out = f"{d}/profile.tsv"
        r = run(arc, out)
        check("exits 0", r.returncode == 0, r.stderr)
        check("tsv written", os.path.exists(out))
        prof = open(out).read()

        # self-interrogate:timeline-gap = 0 real / 4 noise -> precision 0.00, hinted
        check("timeline-gap precision 0.00", "self-interrogate:timeline-gap\t0\t4\t0.00" in prof, prof)
        check("timeline-gap hint emitted", "self-interrogate:timeline-gap" in r.stdout and "tightening" in r.stdout)
        # missing-entity = 1 real / 0 noise
        check("missing-entity precision 1.00", "self-interrogate:missing-entity\t1\t0\t1.00" in prof, prof)
        # aggregate self-interrogate = 1 real / 4 noise
        check("self-interrogate aggregate 1/4", "self-interrogate\t1\t4\t0.20" in prof, prof)
        # cross-model = 1 real, latency 2 days
        check("cross-model real + latency", "cross-model\t1\t0\t1.00\t2" in prof, prof)
        # manual (no tag) counted
        check("manual category counted", "manual\t1\t0" in prof, prof)
        # unlabeled pending line ignored (not counted anywhere as real/noise beyond its tag)
        check("pending line excluded from counts",
              "self-interrogate\t1\t4" in prof,  # the pending self-interrogate line not added
              prof)

        # empty archive -> header only, no hints, exit 0
        emp = f"{d}/empty.md"; open(emp, "w").write("# Archive\n")
        r2 = run(emp)
        check("empty archive exits 0", r2.returncode == 0)
        check("empty archive: header only", r2.stdout.strip().startswith("source\treal"))
        check("empty archive: no hints", "none" in r2.stdout)

        # missing archive file -> graceful (exit 0, header)
        r3 = run(f"{d}/nope.md")
        check("missing archive exits 0", r3.returncode == 0)
    finally:
        shutil.rmtree(d)
    print()
    if fails:
        print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
