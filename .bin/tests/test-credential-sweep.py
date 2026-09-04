#!/usr/bin/env python3
"""Self-check for the JSON credential-store class in .bin/credential-sweep.sh.

    python3 .bin/tests/test-credential-sweep.py

Added for security-audit finding 17 (2026-09-03). The Vercel CLI writes a deploy
token and a refresh token into a JSON file under ~/Library, and that store was
invisible to the sweep twice over: it was not in the store list, and its shape is
not the NAME=VALUE the parser reads. A Vercel token leaking into a build cache
would have swept clean — the same class of silent blindness the script was
written to prevent in the first place.

Every check drives the real script in a synthetic HOME and BORG_ROOT, so the
behaviour under test is the shipped behaviour, not a reimplementation of it:

  1. a credential-shaped key in a JSON store becomes a live pattern, and a file
     planted with that value is actually found;
  2. the value itself never reaches stdout or stderr — findings are store, key
     path, and file path only;
  3. an ABSENT store is skipped silently, because not every machine has the
     Vercel CLI and a missing optional store is not a failure;
  4. a PRESENT but unparseable store is FATAL (exit 2), never a clean result —
     the asymmetry that makes this class worth having;
  5. a logged-out store ({}) is not an error, but its zero contribution is
     reported rather than passing silently;
  6. only credential-shaped keys are harvested — a long userId or expiresAt must
     not become a grep pattern, or every sweep drowns in false positives;
  7. nested objects and arrays are walked, since no store guarantees flatness;
  8. values shorter than 16 chars are ignored, matching the env-file rule.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / ".bin" / "credential-sweep.sh"

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))


class Workspace:
    """A synthetic HOME + BORG_ROOT the sweep can be pointed at."""

    def __init__(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="credsweep-test-"))
        self.home = self.dir / "home"
        self.root = self.dir / "borg"
        (self.root / "tmp").mkdir(parents=True)
        self.home.mkdir(parents=True)

    def env_store(self, name="API_TOKEN", value="env-store-value-0123456789"):
        (self.home / ".zshenv").write_text("export %s=%s\n" % (name, value))
        return value

    def json_store(self, payload, raw=None):
        p = self.home / "Library" / "Application Support" / "com.vercel.cli"
        p.mkdir(parents=True, exist_ok=True)
        f = p / "auth.json"
        f.write_text(raw if raw is not None else json.dumps(payload))
        return f

    def plant(self, value, relpath="cache/build.log"):
        f = self.root / relpath
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("noise\nleaked %s\nmore noise\n" % value)
        return f

    def run(self):
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["BORG_ROOT"] = str(self.root)
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            capture_output=True, text=True, env=env, cwd=str(self.root),
        )

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


TOKEN = "vercel-synthetic-token-AAAABBBBCCCCDDDD-not-a-real-secret"
REFRESH = "vercel-synthetic-refresh-EEEEFFFFGGGGHHHH-not-a-real-secret"


def test_json_token_is_detected():
    w = Workspace()
    try:
        w.json_store({"token": TOKEN, "refreshToken": REFRESH,
                      "userId": "u_1", "expiresAt": 1234567890})
        planted = w.plant(TOKEN)
        r = w.run()
        out = r.stdout + r.stderr
        check("json token becomes a pattern and the planted file is found",
              r.returncode == 1 and str(planted) in r.stdout,
              "rc=%s\n%s" % (r.returncode, out[-1500:]))
        check("finding names the store and key path",
              "com.vercel.cli/auth.json:token" in r.stdout,
              "exposes line missing; got:\n%s" % out[-1500:])
        check("both token and refreshToken are harvested",
              "credential value(s) from 4 candidate store(s)" in r.stdout
              and "json store:" in r.stdout and "-> 2 credential value(s)" in r.stdout,
              out[:1200])
    finally:
        w.close()


def test_value_is_never_printed():
    w = Workspace()
    try:
        w.json_store({"token": TOKEN, "refreshToken": REFRESH})
        w.plant(TOKEN)
        r = w.run()
        out = r.stdout + r.stderr
        check("the credential value never reaches stdout/stderr",
              TOKEN not in out and REFRESH not in out,
              "a value leaked into output")
    finally:
        w.close()


def test_absent_store_is_skipped():
    w = Workspace()
    try:
        w.env_store()
        r = w.run()
        check("absent JSON store is skipped cleanly (exit 0)",
              r.returncode == 0 and "json store:" not in r.stdout,
              "rc=%s\n%s" % (r.returncode, (r.stdout + r.stderr)[-1200:]))
    finally:
        w.close()


def test_unparseable_store_is_fatal():
    for label, raw in (("malformed", "{not json at all"), ("empty", "")):
        w = Workspace()
        try:
            w.env_store()
            w.json_store(None, raw=raw)
            r = w.run()
            check("a present but %s JSON store is FATAL, never clean" % label,
                  r.returncode == 2 and "could not be parsed" in r.stderr,
                  "rc=%s\n%s" % (r.returncode, (r.stdout + r.stderr)[-1200:]))
        finally:
            w.close()


def test_logged_out_store_is_reported_not_fatal():
    w = Workspace()
    try:
        w.env_store()
        w.json_store({})
        r = w.run()
        check("a logged-out ({}) store is not an error but is reported",
              r.returncode == 0 and "-> 0 credential value(s)" in r.stdout,
              "rc=%s\n%s" % (r.returncode, (r.stdout + r.stderr)[-1200:]))
    finally:
        w.close()


def test_non_credential_keys_are_ignored():
    w = Workspace()
    try:
        w.env_store()
        # Long, distinctive, but NOT credential-shaped key names.
        uid = "user-identifier-that-is-plenty-long-0123456789"
        w.json_store({"userId": uid, "expiresAt": "2026-09-03T09:11:23.000Z"})
        planted = w.plant(uid)
        r = w.run()
        check("a long non-credential key does not become a pattern",
              r.returncode == 0 and str(planted) not in r.stdout,
              "rc=%s (userId was swept as if it were a secret)\n%s"
              % (r.returncode, (r.stdout + r.stderr)[-1200:]))
    finally:
        w.close()


def test_nested_and_short_values():
    w = Workspace()
    try:
        nested = "nested-api-key-value-IIIIJJJJKKKK-synthetic"
        w.json_store({
            "accounts": [{"credentials": {"apiKey": nested}}],
            "shortToken": "tooshort",          # < 16 chars, must be ignored
        })
        planted = w.plant(nested)
        r = w.run()
        check("nested objects and arrays are walked",
              r.returncode == 1 and str(planted) in r.stdout,
              "rc=%s\n%s" % (r.returncode, (r.stdout + r.stderr)[-1200:]))
        check("the nested key path is reported",
              "accounts.0.credentials.apiKey" in r.stdout,
              (r.stdout + r.stderr)[-1200:])
        check("values shorter than 16 chars are ignored",
              "-> 1 credential value(s)" in r.stdout,
              "short value was harvested\n%s" % (r.stdout)[:1200])
    finally:
        w.close()


def main():
    if not SCRIPT.exists():
        print("FAIL  cannot find %s" % SCRIPT)
        return 1
    for fn in (test_json_token_is_detected,
               test_value_is_never_printed,
               test_absent_store_is_skipped,
               test_unparseable_store_is_fatal,
               test_logged_out_store_is_reported_not_fatal,
               test_non_credential_keys_are_ignored,
               test_nested_and_short_values):
        fn()

    failed = [r for r in _results if not r[1]]
    for name, ok, detail in _results:
        if not ok:
            print("FAIL  %s\n      %s" % (name, detail))
    print("\n%d/%d checks passed." % (len(_results) - len(failed), len(_results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
