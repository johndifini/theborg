#!/usr/bin/env python3
"""Scan audit output for private data that must never leave the private overlays.

Migration step 6 of `c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md` requires proof —
not assertion — that a run of the monthly memory-governance audit puts no private
path, id, rationale, or content into the tracked snapshot, the logs, or the email.
This scanner supplies that proof by deriving its needles from the live private
overlays and the private artifacts they point at, then searching a given output
file for them.

It never prints a matched needle. A finding is reported as a category, a line
number, and the first 12 hex characters of the needle's SHA-256, so a failure is
locatable without the failure report itself becoming the leak.

Profiles decide which categories are fatal, because the three destinations do not
share one rule:

  email     the report body and subject. The orchestrator's own STAGE 9 scan bans
            home-directory fragments here as well as private material.
  snapshot  the generated `memory-inventory.json`. Same rule as email: it is
            durable generated state that the design treats as publishable.
  log       a raw execution trace. Repository-root paths are expected here (they
            are in every command line), so `home_dir` is reported and not fatal;
            private material is still fatal.

Usage:
  audit-privacy-scan.py --profile email|snapshot|log FILE [FILE ...]
  audit-privacy-scan.py --list-categories

Exit status is 0 when every scanned file passes its profile, 1 on any fatal
finding, and 2 on a usage or environment error.
"""

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import sys

CATEGORIES = (
    "private_id",
    "private_path",
    "private_judgment",
    "private_content",
    "private_marker",
    "local_wrapper",
    "home_dir",
)

FATAL_BY_PROFILE = {
    "email": set(CATEGORIES),
    "snapshot": set(CATEGORIES),
    "log": set(CATEGORIES) - {"home_dir"},
}

# Fields that hold human judgment about a private artifact. Their text is as
# disclosive as the artifact itself.
JUDGMENT_FIELDS = ("rationale", "provenance", "risk", "success_signals",
                   "retirement_triggers", "remediation_policy")

MIN_JUDGMENT = 20   # shorter strings collide with ordinary prose
MIN_CONTENT = 40    # shorter lines collide with boilerplate and headings

# `.private/` is a leak only when a concrete owner directory sits in front of it.
# The design documents the overlay location generically — `<agent>/.private/…`,
# `<owner>/.private/…`, `*/.private/…` — and the orchestrator is required to name
# that shape so a reader can find the mechanism. Flagging the placeholder would
# make the scanner fail on correct documentation, so only a real owner counts.
PRIVATE_MARKER_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)/\.private/")

# `CLAUDE.local.md` is the same story one level down. Named on its own it is the
# name of a category — the orchestrator, this scanner, and the design all have to
# say it. Named with a directory in front of it, it points at one real private
# wrapper, which is the thing STAGE 9 is scanning for.
LOCAL_WRAPPER_RE = re.compile(r"[A-Za-z0-9_.~-]/CLAUDE\.local\.md")


def load_tool(root):
    """Import build-memory-inventory.py for its dependency-free YAML reader.

    The overlays are written by that tool's own writer, so its reader is the
    parser guaranteed to agree with them — and it keeps this scanner runnable on
    a machine with no PyYAML, which is how the first step-6 attempt stalled.
    """
    path = os.path.join(root, ".bin", "build-memory-inventory.py")
    spec = importlib.util.spec_from_file_location("bmi", path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def build_needles(root, bmi):
    """Derive every needle from the live overlays, not from a hard-coded list."""
    needles = {name: set() for name in CATEGORIES}
    overlays = sorted(glob.glob(os.path.join(root, "*", ".private",
                                             "memory-inventory.yaml")))
    if not overlays:
        raise SystemExit("no private overlay found under %s — nothing to prove"
                         % root)

    for overlay in overlays:
        with open(overlay, encoding="utf-8") as handle:
            data = bmi.load_yaml(handle.read(), overlay) or {}
        for artifact_id, record in (data.get("artifacts") or {}).items():
            if not isinstance(record, dict):
                continue
            needles["private_id"].add(str(artifact_id))

            rel = record.get("path")
            if isinstance(rel, str) and rel:
                needles["private_path"].add(rel)
                needles["private_path"].add(os.path.join(root, rel))
                needles["private_content"].update(content_lines(root, rel))

            for field in JUDGMENT_FIELDS:
                for text in walk_strings(record.get(field)):
                    text = text.strip()
                    if len(text) >= MIN_JUDGMENT:
                        needles["private_judgment"].add(text)

    # Concrete owners only — see PRIVATE_MARKER_RE.
    for entry in os.listdir(root):
        if os.path.isdir(os.path.join(root, entry, ".private")):
            needles["private_marker"].add(entry)

    # Pattern-matched, not substring-matched; recorded so the needle
    # counts printed with a result stay honest about what ran.
    needles["local_wrapper"].add(LOCAL_WRAPPER_RE.pattern)
    needles["home_dir"].add(os.path.expanduser("~") + "/")
    return needles


def content_lines(root, rel):
    """Distinctive lines from a private artifact, for content-leak detection."""
    abs_path = os.path.join(root, rel)
    if not os.path.isfile(abs_path):
        return set()
    lines = set()
    try:
        with open(abs_path, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if len(line) >= MIN_CONTENT:
                    lines.add(line)
    except OSError:
        return set()
    return lines


def fingerprint(needle):
    return hashlib.sha256(needle.encode("utf-8")).hexdigest()[:12]


def scan(path, needles, fatal):
    """Return (findings, error). A finding names a category, never its text."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        return [], str(exc)

    findings = []

    # Two categories are pattern matches rather than substring matches, because
    # their bare form is a category name that correct documentation must use.
    for lineno, line in enumerate(lines, 1):
        for match in PRIVATE_MARKER_RE.finditer(line):
            owner = match.group(1)
            if owner in needles["private_marker"]:
                findings.append({
                    "category": "private_marker",
                    "line": lineno,
                    "needle_sha256_12": fingerprint(match.group(0)),
                    "fatal": "private_marker" in fatal,
                })
        for match in LOCAL_WRAPPER_RE.finditer(line):
            findings.append({
                "category": "local_wrapper",
                "line": lineno,
                "needle_sha256_12": fingerprint(match.group(0)),
                "fatal": "local_wrapper" in fatal,
            })

    for category in CATEGORIES:
        if category in ("private_marker", "local_wrapper"):
            continue
        for needle in needles[category]:
            if not needle:
                continue
            for lineno, line in enumerate(lines, 1):
                if needle in line:
                    findings.append({
                        "category": category,
                        "line": lineno,
                        "needle_sha256_12": fingerprint(needle),
                        "fatal": category in fatal,
                    })
                    break   # one finding per needle is enough to fail
    return findings, None


SELF_TEST_OVERLAY = """version: 1
artifacts:
  synthetic-private-note:
    path: syntheticagent/.private/note.md
    type: private_memory
    visibility: private
    rationale: "Synthetic judgment text that exists only for the scanner self test."
    retirement_triggers:
      - "Synthetic retirement condition that never actually becomes true."
"""

SELF_TEST_ARTIFACT = ("A synthetic private content line long enough to be a "
                      "distinctive fingerprint.\n")


def self_test():
    """Prove the scanner detects each category, using synthetic data only.

    Live data cannot exercise `private_judgment`: every private record in this
    workspace is still a `draft`, and drafts carry none of the six judgment
    fields by design. A synthetic tree keeps that channel tested anyway, and
    keeps the whole self test free of real private material.
    """
    import shutil
    import tempfile

    root = tempfile.mkdtemp(prefix="audit-privacy-selftest.")
    try:
        os.makedirs(os.path.join(root, ".bin"))
        real_tool = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "build-memory-inventory.py")
        shutil.copy(real_tool, os.path.join(root, ".bin",
                                            "build-memory-inventory.py"))

        priv = os.path.join(root, "syntheticagent", ".private")
        os.makedirs(priv)
        with open(os.path.join(priv, "memory-inventory.yaml"), "w",
                  encoding="utf-8") as handle:
            handle.write(SELF_TEST_OVERLAY)
        with open(os.path.join(priv, "note.md"), "w", encoding="utf-8") as handle:
            handle.write(SELF_TEST_ARTIFACT)

        bmi = load_tool(root)
        needles = build_needles(root, bmi)

        leaky = os.path.join(root, "leaky-report.txt")
        with open(leaky, "w", encoding="utf-8") as handle:
            handle.write("id: synthetic-private-note\n")
            handle.write("path: syntheticagent/.private/note.md\n")
            handle.write("Synthetic judgment text that exists only for the "
                         "scanner self test.\n")
            handle.write(SELF_TEST_ARTIFACT)
            handle.write("syntheticagent/CLAUDE.local.md\n")
            handle.write("%s/somewhere\n" % os.path.expanduser("~"))

        clean = os.path.join(root, "clean-report.txt")
        with open(clean, "w", encoding="utf-8") as handle:
            handle.write("Coverage: 621/621; 0 unregistered\n")
            handle.write("Private review: 3 draft count(s), paths withheld\n")
            handle.write("Overlays live at <owner>/.private/memory-inventory.yaml\n")
            handle.write("A private wrapper is named CLAUDE.local.md by convention\n")

        failures = []

        found, _ = scan(leaky, needles, FATAL_BY_PROFILE["email"])
        detected = {f["category"] for f in found}
        for category in CATEGORIES:
            if category not in detected:
                failures.append("leaky file: %s not detected" % category)

        found, _ = scan(clean, needles, FATAL_BY_PROFILE["email"])
        for finding in found:
            failures.append("clean file: false positive %s on line %d"
                            % (finding["category"], finding["line"]))

        for line in ("category coverage: %d/%d" % (len(detected), len(CATEGORIES)),):
            print(line)
        for failure in failures:
            print("FAIL %s" % failure)
        print("self-test: %s" % ("FAIL" if failures else "PASS"))
        return 1 if failures else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=sorted(FATAL_BY_PROFILE))
    parser.add_argument("--root", default=os.environ.get("BORG_ROOT"),
                        help="workspace root (default: $BORG_ROOT, else the "
                             "parent of this script's .bin directory)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable results")
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="prove every category detects and none false-positives, "
                             "using a synthetic tree and no real private data")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.list_categories:
        for name in CATEGORIES:
            print(name)
        return 0
    if not args.profile or not args.files:
        parser.error("--profile and at least one FILE are required")

    root = args.root or os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))
    root = os.path.realpath(root)

    bmi = load_tool(root)
    needles = build_needles(root, bmi)
    fatal = FATAL_BY_PROFILE[args.profile]

    results = {}
    failed = False
    for path in args.files:
        findings, error = scan(path, needles, fatal)
        if error is not None:
            results[path] = {"error": error}
            failed = True
            continue
        fatal_count = sum(1 for f in findings if f["fatal"])
        results[path] = {
            "verdict": "FAIL" if fatal_count else "PASS",
            "fatal_findings": fatal_count,
            "advisory_findings": len(findings) - fatal_count,
            "findings": findings,
        }
        failed = failed or bool(fatal_count)

    summary = {
        "profile": args.profile,
        "needles": {name: len(values) for name, values in needles.items()},
        "results": results,
        "verdict": "FAIL" if failed else "PASS",
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("profile: %s" % args.profile)
        print("needles: " + ", ".join("%s=%d" % (name, len(needles[name]))
                                      for name in CATEGORIES))
        for path, result in results.items():
            if "error" in result:
                print("  %s: ERROR %s" % (path, result["error"]))
                continue
            print("  %s: %s (%d fatal, %d advisory)"
                  % (path, result["verdict"], result["fatal_findings"],
                     result["advisory_findings"]))
            for finding in result["findings"]:
                print("      %-18s line %-6d sha256:%s%s"
                      % (finding["category"], finding["line"],
                         finding["needle_sha256_12"],
                         "" if finding["fatal"] else "  (advisory)"))
        print("verdict: %s" % summary["verdict"])

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
