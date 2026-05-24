# Security Policy

## Reporting a vulnerability

Please report security issues privately via **GitHub's private security advisory** workflow on this repo (Security → Report a vulnerability). Do not open a public issue.

The Borg is a personal AI workspace template maintained as a side project. Responses are best-effort; please don't expect an SLA. Coordinated disclosure is appreciated.

## Threat model

The Borg is a workspace template — there is no hosted service, no authentication surface, no users-of-users. "Vulnerability" here means code or configuration that would:

- cause a forker to leak secrets they didn't intend to publish,
- cause Claude to execute untrusted prompt content as if it were trusted instructions,
- silently grant Claude more capability than the workspace owner intended (e.g. a scheduled task re-enabling a disabled MCP server, or a hook running outside its declared scope).

## Forker checklist — before your first commit

If you've cloned or forked this repo, run through this once:

1. Install the pre-commit hook (one-time, per clone):
   `git config core.hooksPath .githooks`
2. Install gitleaks: `brew install gitleaks` (or see https://github.com/gitleaks/gitleaks).
3. Confirm these patterns are still gitignored: `warren-bot-fett/PORTFOLIO.md`, `**/logs/`, `**/.claude/settings.local.json`, `**/.claude/.credentials*`.
4. Anything you drop into `cerebruh/ingest/` is gitignored by default — wiki publishing is opt-in only.
5. If you un-ignore a wiki under `cerebruh/wikis/<topic>/`, do a PII pass first.
6. Enable GitHub secret scanning and push protection on your fork (Settings → Code security).

## What counts as a secret in this workspace

Gitleaks' defaults catch API keys and tokens but miss most of the things that matter here. Treat the following as secrets:

- Google Docs / Sheets / Drive share URLs (the custom `google-docs-url` rule in `.gitleaks.toml` covers these).
- Brokerage account nicknames, holdings, trust references, portfolio weights.
- Personal email addresses, phone numbers, home addresses (beyond what `mrs-beast/USER.md` already publishes by design).
- `*.prompt` file content that names a real person's accounts or strategies.
- Claude Code session history under `~/.claude/projects/` (lives outside the repo by default — keep it that way).

## Defense in depth

Four layers, in order. Each catches what the previous one missed:

1. **`.gitignore`** — keeps sensitive files out of the staging area entirely.
2. **`.githooks/pre-commit` + `.gitleaks.toml`** — blocks staged secrets at commit time, including the custom Google-URL rule.
3. **GitHub secret scanning + push protection** — blocks at push time. Enable on your fork.
4. **Manual `git diff` review before push** — the only layer that catches what rules can't articulate.

No single layer is sufficient. If you disable one (e.g. `SKIP_GITLEAKS=1`), lean harder on the others.

## If you leak something

1. **Rotate first.** Revoke the Google share link, regenerate the API key, change the password. Do this before scrubbing history — once a secret is public, it's public.
2. **Then scrub history.** Use `git filter-repo` (or BFG) to remove the secret from past commits, then force-push.
3. **Assume permanence.** Anything pushed to a public GitHub repo, even briefly, should be considered permanently disclosed. Rotation is the only real remediation.

## Known design choices (not vulnerabilities)

- `mrs-beast/USER.md` contains identity attribution (LinkedIn, X, Reddit, blog). This is intentional — `mrs-beast` is a public-facing social agent.
- The `google-docs-url` rule is intentionally broad and will false-positive on public Google links. False positives are preferred over misses; add fingerprints to `.gitleaksignore` if a public URL is genuinely safe to ship.
- The pre-commit hook can be bypassed with `SKIP_GITLEAKS=1`. This exists for emergencies (e.g. committing a `.gitleaksignore` entry alongside a known false positive). Don't normalize using it.
