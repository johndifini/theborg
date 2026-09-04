# Career dossier deployment runbook

The tracked deployment contract has passed an account-owned, protected Vercel
preview audit. Production is still gated on candidate approval of the public
profile and remaining corpus, landing-page visual and keyboard QA, and the
domain decisions below. Never place private corpus data in Vercel settings or
environment variables.

## Local gate

From `ari/career-dossier/`, run:

```text
npm ci
npm run verify
npm run verify-deployment
```

The second command verifies the corpus. The third rebuilds `dist/` and verifies
the Vercel build contract, route headers, upload allowlist, and exact six-file
served inventory.

## Vercel project settings

Import The Borg GitHub repository as one Vercel project and set:

```text
Root Directory:    ari/career-dossier
Framework Preset:  Other
Build Command:     npm run build
Output Directory:  dist
Install Command:   npm ci
Production branch: repository default branch
```

The tracked `vercel.json` repeats the framework, install, build, output, route,
header, cache, and ignored-build settings so previews cannot silently drift
from the reviewed configuration. The ignored build command exits successfully
when the latest commit has no change below the configured Root Directory, which
cancels that unrelated deployment.

## Preview audit

Create a preview only after confirming its content is synthetic or explicitly
approved for publication. Substitute the preview origin below and verify:

```text
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' "$PREVIEW_ORIGIN/"
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' "$PREVIEW_ORIGIN/agent"
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' "$PREVIEW_ORIGIN/career.json"
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' "$PREVIEW_ORIGIN/career.md"
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' "$PREVIEW_ORIGIN/evidence.json"
curl --fail --silent --show-error --location --output /dev/null --write-out '%{http_code}\n' "$PREVIEW_ORIGIN/llms.txt"
curl --fail --silent --show-error --head "$PREVIEW_ORIGIN/"
curl --fail --silent --show-error --head "$PREVIEW_ORIGIN/career.json"
```

Require status 200 for all six routes; the declared media type for each route;
`X-Content-Type-Options: nosniff`; the reviewed Content Security Policy; and the
bounded cache policy. Also request representative source paths such as
`/src/build.ts`, `/schemas/public-claim.schema.json`, and `/package.json` and
require 404 responses. Inspect the deployment source list to confirm only the
allowlisted remote-build inputs were uploaded and the served output contains
only the six `dist/` files.

### Audit result — 2026-09-02

- The deployment target was `preview`, status `Ready`, with Vercel deployment
  protection and `X-Robots-Tag: noindex` enabled.
- `/`, `/agent`, `/career.json`, `/career.md`, `/evidence.json`, and `/llms.txt`
  returned 200 with their declared media types.
- The reviewed Content Security Policy, `Referrer-Policy: no-referrer`,
  `X-Content-Type-Options: nosniff`, HSTS, and bounded cache headers were present.
- `/src/build.ts`, `/schemas/public-claim.schema.json`, and `/package.json`
  returned 404.
- All six deployed artifacts matched the local generated files byte-for-byte
  except `/`: Vercel appended its platform-owned preview feedback-script tag to
  `index.html`. `/agent` returned the same landing page without that injection
  and matched `dist/agent.html` exactly.
- The first remote build exposed that slash-plus-glob negations did not restore
  allowlisted directories. The corrected `.vercelignore` uses Vercel's documented
  `!directory` form and the successful upload contained all required build inputs.
- GitHub auto-linking did not complete because the Vercel account does not yet
  have a GitHub login connection. Direct CLI preview deployment succeeded.
- Vercel classified the project's first, failed build as Production. That build
  never served the dossier and its exact deployment record was removed. The
  account now contains only the ready Preview deployment.

## Production release

After the content, design, and preview gates pass:

1. Add `agent.johndifini.com` to the Vercel project.
2. Copy the exact DNS record Vercel displays into the domain's authoritative DNS
   provider; do not infer or pre-document the target value.
3. Wait for Vercel to report valid DNS and TLS.
4. Verify that `https://agent.johndifini.com` serves the canonical landing page
   directly and rerun the route and header audit against the production origin.

If any production check fails, restore the last known-good Vercel deployment
before retrying. No Squarespace URL mapping is part of the current release; the
earlier `johndifini.com/agent` redirect idea is deferred and may be revisited.

### Production audit result — 2026-09-04: FAILED, no production deployment

Steps 1–3 above passed. Step 4 failed because the project has no production
deployment; the domain is attached to an empty production alias.

Passing:

- `agent.johndifini.com` resolves to the Vercel edge via the CNAME Vercel
  issued, with a record TTL of 600 (GoDaddy's floor; the zone's SOA minimum is
  also 600).
- TLS is valid and terminated by Vercel. Let's Encrypt issued
  `CN=agent.johndifini.com` on 2026-09-04, valid through 2026-12-03. `curl`
  verified the chain with no override.
- HSTS (`max-age=63072000`) is present.

Failing:

- All six documented routes — `/`, `/agent`, `/career.json`, `/career.md`,
  `/evidence.json`, `/llms.txt` — return **404** with
  `x-vercel-error: DEPLOYMENT_NOT_FOUND` and a `text/plain` platform error body.
- The per-route `Content-Type`, `Cache-Control`, `Vercel-CDN-Cache-Control`,
  Content Security Policy, and `Referrer-Policy` headers from `vercel.json` are
  therefore absent. Only the platform's own `cache-control`,
  `strict-transport-security`, and `server` headers are returned.
- The source-exposure probes (`/src/build.ts`, `/package.json`,
  `/schemas/public-claim.schema.json`) do return 404, but this is **not**
  evidence that the allowlist works — every path 404s equally, so the check is
  vacuous until a real deployment serves the domain.

Cause: this is the unresolved consequence of the 2026-09-02 note above. The
project's only surviving deployment is the protected Preview; the failed first
build that Vercel had classified as Production was removed, leaving production
empty. Assigning a custom domain points it at the production alias, which
resolves to nothing.

Blocking prerequisite discovered during this audit: the approved corpus has
never been committed. At `3a251e1`, `main` still contains the nine-claim
synthetic corpus with the `Alex Example` profile and the `EX-*` records, while
the 70-claim John DiFini build exists only as uncommitted working-tree changes.
A Git-connected production build from `main` in this state would publish
synthetic data to the live domain.

Required order before re-running this audit:

1. Commit the `ari/career-dossier/` changes and push to `main`.
2. Complete the GitHub login connection and link the repository to the project
   so `main` builds as Production.
3. Confirm the production deployment is `Ready` and aliased to
   `agent.johndifini.com`.
4. Re-run the route, header, source-exposure, and byte-comparison audit. Only a
   run where the six routes return 200 with their declared media types makes the
   404 source probes meaningful.

### Build failure and `.vercelignore` removal — 2026-09-04

The first Git-connected production build of `2e31828` failed in one second:

```text
Cloning github.com/johndifini/theborg (Branch: main, Commit: 2e31828)
Found .vercelignore
Removed 415 ignored files defined in .vercelignore
Running "git diff --quiet HEAD^ HEAD ./"
warning: Not a git repository. Use --no-index to compare two paths outside a working tree
```

`.vercelignore` is resolved against the **deployment** root for a CLI deploy but
against the **repository** root for a Git-connected build. The allowlist was
written for the CLI path, so on the Git build `/*` swept the repository root —
the removal log names workspace paths such as `/.bin/notify-email.sh`, not
project paths — while `!content`, `!src`, and the other negations pointed at
repository-root directories that do not exist. It removed 415 files against 388
tracked files, so `.git` went with them and `ignoreCommand` had no repository to
inspect.

The file is removed rather than repaired. It could not do its stated job on a
Git build: excluding documentation and fixtures from the upload never controlled
what is reachable, because Vercel serves `outputDirectory` alone. That is the
control the 2026-09-02 preview audit actually exercised when `/src/build.ts` and
`/package.json` returned 404. Build inputs are now scoped by the project's Root
Directory. ADR-0001 §8 is amended accordingly, and `tests/deployment.test.ts`
asserts the file stays absent and that `outputDirectory` remains `dist`.

`ignoreCommand` is unchanged. With `.git` present it can run, but whether
`HEAD^` resolves in Vercel's clone depth is still unproven; the next build's log
settles it.
