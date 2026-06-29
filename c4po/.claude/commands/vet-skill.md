---
description: Security pre-install audit of a third-party Claude Code skill or plugin.
---

Security-audit a third-party skill/plugin **before** it touches this machine.
`$ARGUMENTS` = its name, repo, or local path.

1. **Ascertain the upstream source yourself** (don't just ask). Distinguish the
   canonical repo from mirrors / re-hosts; audit only upstream.
2. **Read SKILL.md / plugin manifest** — what it EXECUTES (Bash, network, external
   services) and what it READS (file scope: stays in its project vs roams
   home / `.claude` / credentials). A read-only tool making outbound calls is a flag.
3. **Audit bundled scripts** for outbound endpoints, secret handling (Keychain / `.env`
   writes), and any setup wizard — read the wizard before the user runs it.
4. **Audit `hooks/`** — anything in `hooks.json` auto-runs with no per-use approval.
   Read each hook. Flag network calls and secret reads: `find-generic-password` WITH
   `-w` exfiltrates a secret; without `-w` it only tests existence.
5. **Note runtime + credential requirements** and where config / secrets land (path,
   perms).
6. **Run the read-only dry-run** (e.g. `--preflight`) before any real run; confirm no
   writes and no cookie reads.
7. **Verdict** — malware-shaped? footprint? least-privilege config (browser-cookie
   mode over pasted tokens; a burner account for ToS-violating scrapers). Recommend
   install / install-with-changes / decline.
