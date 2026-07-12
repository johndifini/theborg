#!/usr/bin/env python3
"""Emit grep patterns for distinctive PHI targets + encoded variants.

Shared generator used by post-ingest-verify.sh (wiki-wide tripwire) and
pre-commit.sh (staged-files gate). Output is MODE<TAB>PATTERN lines:

    SUB   pattern is matched as a substring   (grep -F)
    WORD  pattern is matched whole-word       (grep -wF)

Pattern values must only ever flow into temp files handed to `grep -f` —
never into logs, chat output, or committed files.

Why encoded variants: the 2026-06-11 leak got past whole-word matching as
URL-encoded HL7 name segments (%5E...%5E), plus-encoded addresses, and the
compact digit-only DOB form. Variants are derived at RUNTIME from the
git-ignored targets file, so no encoded PHI is ever stored anywhere.

Selection rules mirror the original post-ingest-verify generator:
  * dobs/phones/mrns/medicaid — distinctive raw IDs, substring match
  * names/addresses — only multi-token >=8-char leaves, whole-word match
    (atomized single-token fragments collide with prose; their *encoded*
    forms are distinctive though, so single-token name aliases >=6 chars
    contribute %5E-delimited variants only)
"""
import json
import re
import sys
import urllib.parse

REPL = re.compile(
    r'^(PATIENT|MOM|DAD|PARENT|PERSON|CHILD|SPOUSE|SIBLING|FRIEND|PROVIDER)-\d+$'
    r'|^REDACTED-|^ADDRESS-'
    # Codename strings may EMBED a bracketed token rather than start with one
    # ("Father [REDACTED-NAME]" — the 2026-06-12 family-history entries).
    # Any string containing a redaction token is a replacement, not a value;
    # .* prefix is required because callers use REPL.match() (start-anchored).
    r'|.*\[(REDACTED|ADDRESS)-', re.I)


# Keys whose values are NOT target values: replacements ("codename"),
# deliberately-protected phrases ("exceptions" — e.g. a different real person
# sharing a target's name, kept in the wiki on purpose), and metadata/notes
# (underscore-prefixed). Harvesting them turns the gate against its own
# replacement text and against content the curator chose to keep.
SKIP_KEYS = {"codename", "exceptions"}


def strs(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k in SKIP_KEYS or k.startswith("_"):
                continue
            yield from strs(v)
    elif isinstance(x, list):
        for v in x:
            yield from strs(v)


def main():
    d = json.load(open(sys.argv[1]))
    out = []

    def add(mode, s):
        out.append((mode, s))

    def encoded(s):
        q = urllib.parse.quote(s, safe="")
        if q != s:
            add("SUB", q)
        if " " in s:
            add("SUB", s.replace(" ", "+"))

    # distinctive raw IDs -> substring; digit-compact form -> whole-word
    for key in ("dobs", "phones", "mrns", "medicaid"):
        for s in strs(d.get(key, [])):
            s = s.strip()
            if len(s) >= 4 and not s.startswith("[") and not REPL.match(s):
                add("SUB", s)
                encoded(s)
                digits = re.sub(r"\D", "", s)
                if len(digits) >= 7 and digits != s:
                    add("WORD", digits)

    # names/addresses: full multi-token leaves whole-word; encoded as substring
    for key in ("names", "addresses"):
        for s in strs(d.get(key, [])):
            s = s.strip()
            if s.startswith("[") or REPL.match(s):
                continue
            if " " in s and len(s) >= 8:
                add("WORD", s)
                encoded(s)
                if key == "names":
                    parts = s.split()
                    if 2 <= len(parts) <= 3:
                        for sep in ("^", "%5E"):
                            add("SUB", sep.join(parts))
                            add("SUB", sep.join(reversed(parts)))
            elif key == "names" and " " not in s and len(s) >= 6:
                # single-token alias: only HL7-delimited encoded forms are
                # distinctive enough to grep without prose collisions
                add("SUB", f"%5E{s}")
                add("SUB", f"{s}%5E")

    seen = set()
    for mode, s in out:
        if (mode, s) not in seen:
            seen.add((mode, s))
            print(f"{mode}\t{s}")


if __name__ == "__main__":
    main()
