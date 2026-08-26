#!/usr/bin/env python3
"""Self-check for .bin/build-memory-inventory.py.

    python3 .bin/tests/test-build-memory-inventory.py

Proves the three things migration step 1 of
`c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md` has to establish before discovery
is worth writing:

  1. the YAML subset reader parses what the registry uses and fails loudly —
     never silently — on anything it does not implement;
  2. the validator rejects a malformed record for each rule the schema and the
     cross-record layer are supposed to enforce, and accepts a valid one;
  3. the real registry and the synthetic private overlay in this repo validate
     clean, end to end, through the CLI's exit codes.

No third-party dependencies: this workspace has neither PyYAML nor jsonschema
and cannot install them, which is why the tool implements both subsets itself.
"""

from __future__ import annotations

import copy
import datetime as _dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.dirname(HERE)
ROOT = os.path.dirname(BIN)
TOOL = os.path.join(BIN, "build-memory-inventory.py")

_spec = importlib.util.spec_from_file_location("build_memory_inventory", TOOL)
bmi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bmi)

SCHEMA = json.load(open(os.path.join(ROOT, "MEMORY-INVENTORY.schema.json"), encoding="utf-8"))
TODAY = _dt.date(2026, 8, 26)

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition), detail))


# --------------------------------------------------------------------------
# 1. YAML subset reader
# --------------------------------------------------------------------------

def test_yaml_reader():
    doc = """
# leading comment
version: 1
defaults:
  scoped_rule:
    review_cadence: quarterly     # trailing comment
    review_method: [semantic, usage]
artifacts:
  a-record:
    path: "a/b c.md"
    quoted_hash: "not # a comment"
    single: 'it''s fine'
    empty_flow: []
    explicit_null: null
    tilde_null: ~
    truthy: true
    count: 12
    block_list:
      - first item
      - "second item"
    objects:
      - kind: workspace_decision
        reference: "r one"
      - kind: incident
        reference: "r two"
    same_indent_list:
    - one
    - two
"""
    got = bmi.load_yaml(doc, "t.yaml")
    want = {
        "version": 1,
        "defaults": {"scoped_rule": {"review_cadence": "quarterly",
                                     "review_method": ["semantic", "usage"]}},
        "artifacts": {"a-record": {
            "path": "a/b c.md",
            "quoted_hash": "not # a comment",
            "single": "it's fine",
            "empty_flow": [],
            "explicit_null": None,
            "tilde_null": None,
            "truthy": True,
            "count": 12,
            "block_list": ["first item", "second item"],
            "objects": [{"kind": "workspace_decision", "reference": "r one"},
                        {"kind": "incident", "reference": "r two"}],
            "same_indent_list": ["one", "two"],
        }},
    }
    check("yaml: parses the constructs the registry uses", got == want,
          "got %r" % (got,))

    # A date must stay a string so `format: date` can check it and so the value
    # round-trips through the JSON snapshot unchanged.
    check("yaml: unquoted dates stay strings",
          bmi.load_yaml("d: 2026-08-26")["d"] == "2026-08-26")

    unsupported = [
        ("tab indentation", "a:\n\tb: 1"),
        ("block scalar", "a: |\n  text"),
        ("folded scalar", "a: >\n  text"),
        ("anchor", "a: &anchor 1"),
        ("alias", "a: *anchor"),
        ("tag", "a: !!str 1"),
        ("flow mapping", "a: {b: 1}"),
        ("duplicate key", "a: 1\na: 2"),
        ("unterminated flow sequence", "a: [1, 2"),
        ("bare scalar where a key belongs", "a: 1\nnope"),
        ("over-indented sibling", "a: 1\n  b: 2"),
        ("unterminated double quote", 'a: "b'),
    ]
    for label, text in unsupported:
        try:
            bmi.load_yaml(text, "t.yaml")
            check("yaml: rejects %s" % label, False, "parsed without error")
        except bmi.YamlSubsetError:
            check("yaml: rejects %s" % label, True)


# --------------------------------------------------------------------------
# 2. Schema-support guard
# --------------------------------------------------------------------------

def test_schema_support_guard():
    try:
        bmi.assert_schema_supported(SCHEMA)
        check("schema: the shipped schema uses only implemented keywords", True)
    except bmi.SchemaSupportError as exc:
        check("schema: the shipped schema uses only implemented keywords", False, str(exc))

    # An unimplemented keyword must fail even when it sits in a branch no
    # current record reaches — otherwise it would silently assert nothing.
    buried = {"type": "object",
              "properties": {"x": {"properties": {"y": {"oneOf": [{"type": "string"}]}}}}}
    try:
        bmi.assert_schema_supported(buried)
        check("schema: rejects an unimplemented keyword in an unreached branch", False)
    except bmi.SchemaSupportError:
        check("schema: rejects an unimplemented keyword in an unreached branch", True)

    try:
        bmi.assert_schema_supported({"type": "string", "format": "email"})
        check("schema: rejects an unimplemented format", False)
    except bmi.SchemaSupportError:
        check("schema: rejects an unimplemented format", True)


# --------------------------------------------------------------------------
# 3. Registry validation
# --------------------------------------------------------------------------

def record(**over):
    base = {
        "path": "some/where.md",
        "type": "scoped_rule",
        "owner": "workspace",
        "scope": "workspace",
        "visibility": "public",
        "canonicality": "canonical",
        "rationale": "A rationale long enough to say what failure this prevents.",
        "introduced": "2026-01-01",
        "provenance": [{"kind": "workspace_decision", "reference": "a reference"}],
        "load_mode": "path_triggered",
        "consumers": ["claude-code"],
        "risk": "low",
        "review": {"cadence": "quarterly", "method": ["semantic"], "last_reviewed": None},
        "success_signals": ["An observable signal that it earns its place."],
        "retirement_triggers": ["A concrete condition that would retire it."],
        "remediation_policy": "propose_patch",
        "related": [],
    }
    base.update(copy.deepcopy(over))
    return base


def run(public_artifacts, defaults=None, overlay=None, show_private=False, version=1):
    regs = [bmi.Registry({"version": version, "defaults": defaults or {},
                          "artifacts": public_artifacts},
                         "MEMORY-INVENTORY.yaml", private=False)]
    if overlay is not None:
        regs.append(bmi.Registry({"version": version, "artifacts": overlay},
                                 "c4po/.private/memory-inventory.yaml", private=True))
    return bmi.validate_registries(regs, SCHEMA, TODAY, show_private)


def test_accepts_valid():
    errs = run({"good-rule": record()})
    check("valid: a well-formed record is accepted", errs == [], "; ".join(errs))

    # A generated bridge plus its canonical source, the shape the design needs
    # most: two records, one reviewed semantically and one for drift only.
    errs = run({
        "canonical-rule": record(related=["derived-bridge"]),
        "derived-bridge": record(
            path="a/SKILL.md", type="generated_rule_bridge", canonicality="generated",
            canonical_ref="canonical-rule", load_mode="explicit", consumers=["codex"],
            review={"cadence": "each_audit", "method": ["drift_only"], "last_reviewed": None},
            remediation_policy="auto_safe", related=["canonical-rule"]),
    })
    check("valid: a canonical/generated pair is accepted", errs == [], "; ".join(errs))


def test_rejects_malformed():
    cases = [
        ("missing a required field",
         lambda: run({"rec-one": {k: v for k, v in record().items() if k != "rationale"}}),
         "missing required field 'rationale'"),
        ("an unknown field",
         lambda: run({"rec-one": record(colour="blue")}),
         "unknown field 'colour'"),
        ("a value outside an enum",
         lambda: run({"rec-one": record(type="sticky_note")}),
         "is not one of"),
        ("a rationale too short to be a rationale",
         lambda: run({"rec-one": record(rationale="tidy")}),
         "shorter than"),
        ("an empty provenance list",
         lambda: run({"rec-one": record(provenance=[])}),
         "at least 1 item"),
        ("an empty review.method list",
         lambda: run({"rec-one": record(review={"cadence": "quarterly", "method": [],
                                          "last_reviewed": None})}),
         "at least 1 item"),
        ("a cadence that is neither a named interval nor an on_ trigger",
         lambda: run({"rec-one": record(review={"cadence": "whenever", "method": ["semantic"],
                                          "last_reviewed": None})}),
         "matched none of the allowed forms"),
        ("an impossible calendar date",
         lambda: run({"rec-one": record(introduced="2026-02-30")}),
         "not a YYYY-MM-DD calendar date"),
        ("a date in the future",
         lambda: run({"rec-one": record(introduced="2027-01-01")}),
         "in the future"),
        ("a review that predates the artifact",
         lambda: run({"rec-one": record(review={"cadence": "quarterly", "method": ["semantic"],
                                          "last_reviewed": "2025-06-01"})}),
         "precedes `introduced`"),
        ("an id that disagrees with its map key",
         lambda: run({"rec-one": record(id="something-else")}),
         "the key is the id"),
        ("a malformed artifact id",
         lambda: run({"Not_An_Id": record()}),
         "invalid property name"),
        ("two records claiming one path",
         lambda: run({"rec-one": record(), "rec-two": record()}),
         "already claimed by"),
        ("a generated artifact with no canonical_ref",
         lambda: run({"rec-one": record(canonicality="generated")}),
         "requires `canonical_ref`"),
        ("a canonical artifact carrying a canonical_ref",
         lambda: run({"rec-one": record(canonical_ref="rec-two"), "rec-two": record(path="o.md")}),
         "only meaningful for generated or mirror"),
        ("a canonical_ref that does not resolve",
         lambda: run({"rec-one": record(canonicality="mirror", canonical_ref="ghost")}),
         "does not resolve"),
        ("a related id that does not resolve",
         lambda: run({"rec-one": record(related=["ghost"])}),
         "does not resolve"),
        ("a record related to itself",
         lambda: run({"rec-one": record(related=["rec-one"])}),
         "lists itself"),
        ("a bridge type declared canonical",
         lambda: run({"rec-one": record(type="generated_rule_bridge", canonicality="canonical")}),
         "must have canonicality"),
        ("a raw source declared canonical",
         lambda: run({"rec-one": record(type="knowledge_source", canonicality="canonical",
                                  load_mode="source_only")}),
         "must have canonicality"),
        ("a Cerebruh page the audit could edit unattended",
         lambda: run({"rec-one": record(type="knowledge_page", load_mode="retrieved",
                                  remediation_policy="auto_safe")}),
         "read-only from"),
        ("a private record in the tracked registry",
         lambda: run({"rec-one": record(visibility="private")}),
         "belongs in a gitignored"),
        ("a public record in a private overlay",
         lambda: run({"public-filler": record()},
                     overlay={"priv-one": record(path="priv.md")}, show_private=True),
         "must be `private` or `redacted`"),
        ("private_memory declared public",
         lambda: run({"rec-one": record(type="private_memory", visibility="public")}),
         "requires visibility private or redacted"),
        ("a defaults key that is not an artifact type",
         lambda: run({"rec-one": record()}, defaults={"sticky_note": {"risk": "low"}}),
         "invalid property name"),
        ("a defaults block with an undefaultable field",
         lambda: run({"rec-one": record()}, defaults={"scoped_rule": {"rationale": "nope"}}),
         "unknown field 'rationale'"),
        ("a wrong registry version",
         lambda: run({"rec-one": record()}, version=2),
         "expected the constant"),
    ]
    for label, thunk, expected in cases:
        errs = thunk()
        hit = any(expected in e for e in errs)
        check("rejects %s" % label, hit,
              "expected %r among: %s" % (expected, "; ".join(errs) or "(no errors)"))

    # A tracked record must not be able to name a private one, or the public
    # file would disclose that a private artifact exists.
    errs = run({"rec-one": record(related=["priv-one"])},
               overlay={"priv-one": record(path="p.md", visibility="private")},
               show_private=True)
    check("rejects a tracked record referencing a private overlay id",
          any("points into a private overlay" in e for e in errs),
          "; ".join(errs))

    # Same id declared in both files is a duplicate, not a merge.
    errs = run({"dup-id": record()},
               overlay={"dup-id": record(path="p.md", visibility="private")},
               show_private=True)
    check("rejects the same id in both the registry and an overlay",
          any("duplicate artifact id" in e for e in errs), "; ".join(errs))


def test_overlay_accepts_private_and_redacted():
    for vis in ("private", "redacted"):
        errs = run({"public-filler": record()},
                   overlay={"priv-one": record(path="p.md", type="private_memory",
                                               visibility=vis, load_mode="explicit")},
                   show_private=True)
        check("overlay: accepts a %s private_memory record" % vis, errs == [], "; ".join(errs))

    # An overlay with no records at all is fine; the tracked registry needs one.
    errs = run({"public-filler": record()}, overlay={}, show_private=True)
    check("overlay: an empty overlay is valid", errs == [], "; ".join(errs))
    errs = run({}, overlay={"priv-one": record(path="p.md", visibility="private")},
               show_private=True)
    check("overlay: an empty tracked registry is not valid",
          any("at least 1 propert" in e for e in errs), "; ".join(errs))


def test_defaults_merge():
    thin = {k: v for k, v in record().items()
            if k not in ("risk", "remediation_policy")}
    # cadence and method come from the class default; last_reviewed never can,
    # because it is per-artifact review history rather than class policy.
    thin["review"] = {"last_reviewed": None}
    defaults = {"scoped_rule": {"risk": "high", "remediation_policy": "approval_required",
                                "review_cadence": "quarterly", "review_method": ["semantic"]}}
    errs = run({"rec-one": thin}, defaults=defaults)
    check("defaults: fill fields the record omits", errs == [], "; ".join(errs))

    merged = bmi.apply_defaults(thin, defaults)
    check("defaults: land in the right place",
          merged["risk"] == "high" and merged["review"]["cadence"] == "quarterly",
          repr(merged.get("review")))

    # A record always wins over its class default.
    merged = bmi.apply_defaults(record(risk="critical"), defaults)
    check("defaults: never override a value the record states", merged["risk"] == "critical")

    # A default for a different class must not leak across.
    merged = bmi.apply_defaults(thin, {"knowledge_page": {"risk": "low"}})
    check("defaults: do not apply across artifact classes", "risk" not in merged)

    # Without the default, the same thin record is incomplete — proving the
    # merge is doing real work rather than the schema being lax.
    errs = run({"rec-one": thin})
    check("defaults: a record that relies on a missing default is rejected",
          any("missing required field 'risk'" in e for e in errs), "; ".join(errs))


def test_private_redaction():
    secret_id = "operation-nightingale"
    secret_path = "sensitive/dir/plans.md"
    bad = record(path=secret_path, visibility="private", type="not_a_type")
    errs = run({"public-filler": record()}, overlay={secret_id: bad}, show_private=False)
    leaked = [e for e in errs if secret_id in e or secret_path in e]
    check("private: ids and paths are redacted by default",
          errs and not leaked,
          "leaked: %s" % "; ".join(leaked))

    errs = run({"public-filler": record()}, overlay={secret_id: bad}, show_private=True)
    check("private: --show-private opts back in to full detail",
          any(secret_id in e for e in errs), "; ".join(errs))


# --------------------------------------------------------------------------
# 4. End-to-end through the CLI
# --------------------------------------------------------------------------

def cli(*args):
    proc = subprocess.run([sys.executable, TOOL] + list(args),
                          capture_output=True, text=True, cwd=ROOT)
    return proc.returncode, proc.stdout + proc.stderr


def test_cli():
    code, out = cli("validate", "--today", "2026-08-26")
    check("cli: this repo's registry validates clean", code == 0, out.strip())

    overlay = os.path.join(ROOT, "c4po/.private.example/memory-inventory.example.yaml")
    code, out = cli("validate", "--today", "2026-08-26", "--overlay", overlay)
    check("cli: the synthetic private overlay validates clean", code == 0, out.strip())
    check("cli: it is counted as private, not public", "1 private record" in out, out.strip())

    with tempfile.TemporaryDirectory() as tmp:
        broken = os.path.join(tmp, "broken.yaml")
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write("version: 1\nartifacts:\n  r:\n    path: a.md\n    type: scoped_rule\n")
        code, out = cli("validate", "--registry", broken, "--today", "2026-08-26")
        check("cli: a malformed registry exits 1", code == 1, "exit %d: %s" % (code, out.strip()))
        check("cli: and names the missing fields", "missing required field" in out, out.strip())

        unparseable = os.path.join(tmp, "tabs.yaml")
        with open(unparseable, "w", encoding="utf-8") as fh:
            fh.write("version: 1\nartifacts:\n\tr: 1\n")
        code, out = cli("validate", "--registry", unparseable, "--today", "2026-08-26")
        check("cli: an unparseable registry exits 1 rather than passing", code == 1,
              "exit %d: %s" % (code, out.strip()))

        missing = os.path.join(tmp, "absent.yaml")
        code, out = cli("validate", "--registry", missing)
        check("cli: a missing registry is a usage error, not an invalid one", code == 2,
              "exit %d: %s" % (code, out.strip()))

    code, out = cli("discover")
    check("cli: discover reports that step 2 is not implemented", code == 3, out.strip())


# --------------------------------------------------------------------------

def main():
    for fn in (test_yaml_reader, test_schema_support_guard, test_accepts_valid,
               test_rejects_malformed, test_overlay_accepts_private_and_redacted,
               test_defaults_merge, test_private_redaction,
               test_cli):
        fn()

    failed = [r for r in _results if not r[1]]
    for name, ok, detail in _results:
        if not ok:
            print("FAIL  %s\n      %s" % (name, detail))
    print("\n%d/%d checks passed." % (len(_results) - len(failed), len(_results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
