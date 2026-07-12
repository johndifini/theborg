# GBrain setup — life-wiki

Setup notes for installing and running GBrain (https://github.com/garrytan/gbrain) over `~/life-wiki/wikis/`.

## Why these choices

- **Brain root = `~/life-wiki/wikis/`** (not the repo root). Keeps `ingest/`, `.claude/`, `.obsidian/` out of the index. Sub-wikis (`health/`, `journal/`, `shared/`) become GBrain's top-level dirs — MECE-compatible.
- **Local embeddings** (Ollama / `nomic-embed-text`, 768d) because the wiki holds health PII. Nothing leaves the machine. Swappable to ZeroEntropy / OpenAI later via `gbrain reinit-pglite`.
- **PGLite** (Postgres-in-WASM, file-backed) under `~/.gbrain/`. Zero-config, encrypted at rest by FileVault. Migrate to standalone Postgres when the wiki crosses ~10K pages.

## How gbrain is invoked here

gbrain is installed as a **cloned repo + bun wrapper**, NOT a global bun binary. The sandbox correctly refuses to globally install lifecycle-script-running code from a third-party GitHub repo, so we use:

- Cloned source at `~/gbrain` (deps installed with `bun install --ignore-scripts`)
- Wrapper script at `.claude/scripts/gbrain` → `exec bun run ~/gbrain/src/cli.ts "$@"`
- Add the wrapper to PATH or use the full path

To put `gbrain` on PATH for your shell:

```bash
# Either symlink it (one-time):
ln -s /Users/lashawsalta/life-wiki/.claude/scripts/gbrain ~/.local/bin/gbrain
# (ensure ~/.local/bin is in PATH)

# Or alias it in ~/.zshrc:
alias gbrain="/Users/lashawsalta/life-wiki/.claude/scripts/gbrain"
```

## What's already done (2026-05-23)

- Bun 1.3.14 installed via Homebrew
- Ollama 0.5.7 daemon running, `nomic-embed-text` pulled
- gbrain cloned to `~/gbrain`, deps installed (`bun install --ignore-scripts`)
- `gbrain init --pglite --embedding-model ollama:nomic-embed-text --embedding-dimensions 768` — DONE. DB at `~/.gbrain/brain.pglite`.
- `gbrain import ~/life-wiki/wikis --no-embed` — DONE. 67 pages imported, 0 skipped (confirms `index.md` files ARE indexed by gbrain 0.40.6.0; the docs were outdated).
- `gbrain embed --stale` — DONE. 68 chunks embedded locally via Ollama.

## What's left — run these yourself

The sandbox stopped allowing further `bun run` of gbrain code mid-session. Run these to finish:

```bash
# Replace 'gbrain' below with /Users/lashawsalta/life-wiki/.claude/scripts/gbrain if not on PATH.

# 1. Build the typed-link graph from existing wikilinks
gbrain extract links --source db --dry-run | head -40    # preview first
gbrain extract links --source db
gbrain extract timeline --source db
gbrain stats                                              # confirm links > 0

# 2. Activate live sync + nightly dream cycle
mkdir -p ~/Library/LaunchAgents
cp /Users/lashawsalta/life-wiki/.claude/scripts/com.lashawsalta.gbrain-sync.plist  ~/Library/LaunchAgents/
cp /Users/lashawsalta/life-wiki/.claude/scripts/com.lashawsalta.gbrain-dream.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lashawsalta.gbrain-sync.plist
launchctl load ~/Library/LaunchAgents/com.lashawsalta.gbrain-dream.plist
launchctl list | grep gbrain

# 3. First real query
gbrain query "what conditions do I currently track?"
```

## Import + graph backfill

```bash
gbrain import ~/life-wiki/wikis/ --no-embed
gbrain embed --stale
gbrain extract links --source db --dry-run | head -40   # preview
gbrain extract links --source db
gbrain extract timeline --source db
gbrain stats                                            # confirm links > 0
```

## Verify post-import

1. `gbrain orphans --json` — pages with zero inbound wikilinks. Expect index/meta pages here; flag any entity pages.
2. `gbrain query "<something only in a sub-wiki wiki/index.md>"` — checks whether `index.md` files are indexed. If empty, GBrain is skipping all `index.md`; consider renaming sub-wiki `index.md` → `overview.md`.
3. `gbrain graph-query <some-person-slug> --depth 2` — relationship traversal works.
4. Edit a wiki page, then run `gbrain sync --repo ~/life-wiki/wikis && gbrain embed --stale` (or wait for the daily 03:00 sync), re-query — change reflected.

## Live sync + nightly cycle

**Option A — gbrain's own daemon (simplest):**

```bash
gbrain autopilot --install
```

**Option B — launchd (more control, plists pre-staged in this repo):**

```bash
mkdir -p ~/Library/LaunchAgents
cp .claude/scripts/com.lashawsalta.gbrain-sync.plist  ~/Library/LaunchAgents/
cp .claude/scripts/com.lashawsalta.gbrain-dream.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lashawsalta.gbrain-sync.plist
launchctl load ~/Library/LaunchAgents/com.lashawsalta.gbrain-dream.plist

# Verify:
launchctl list | grep gbrain
tail -f .claude/logs/gbrain-sync.log
```

Sync runs daily at 03:00; dream runs nightly at 03:15. Both log to `.claude/logs/` (already gitignored). (Sync was every 15 min until 2026-06-26 — moved to daily since GBrain is Mac-side recall only and not load-bearing; write-path workflows reindex on demand.)

## Swapping the embedding model later

```bash
gbrain reinit-pglite \
  --embedding-model openai:text-embedding-3-large \
  --embedding-dimensions 3072
# Re-embeds everything once. Cost ≈ $0.02 per 1K wiki pages.
```

## Upgrade

```bash
gbrain upgrade        # binary + migrations + post-upgrade notes
```

## Known caveats

- **`index.md` skip scope** — gbrain's `live-sync.md` says meta files (`README.md`, `index.md`, `schema.md`, `log.md`) are excluded. Whether this is repo-root-only or all-dirs is unclear from the docs. Verify on first `gbrain stats` and adapt.
- **Audio binaries** — `.m4a`/`.mp3`/etc. are not indexed (gbrain reads `.md` only). Transcripts are the source of truth.
- **Health PII** — embedding model must remain local until/unless the curator approves cloud embeddings for clinical content. Don't run `gbrain reinit-pglite` with a cloud provider on a brain containing health pages without explicit OK.
