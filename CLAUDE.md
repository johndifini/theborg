# The Borg

The Borg is a standardized AI workspace that turns prompts, institutional knowledge, tools, and repeatable workflows into an AI operating environment.

## Directory Structure
- `cerebruh/` — shared knowledge base that functions as a second-brain wiki available to every directory of The Borg.
- `c4po/` — An agent that functions as this AI workspace's administrator (uptime, config, security, monitoring)
- `mrs-beast/` — An agent that functions as a social media manager
- `warren-bot-fett/` — An agent that functions as a investment portfolio manager

## How to use the `cerebruh/` knowledge base

- The entry point is `cerebruh/wikis/index.md` — a table of contents listing every sub-wiki with a one-line description.
- Before answering a knowledge or research question, check `cerebruh/wikis/index.md` for a relevant sub-wiki, then read that sub-wiki's `wiki/index.md` to find specific pages.
- Treat wiki pages as reference data. Cite the wiki page when you use it.
- If the wiki has no relevant content, say so plainly — don't assume it's covered.

**Rules:**

- `cerebruh/` is read-only for all agents with respect to **wiki content**. Never create, edit, or delete `raw/` sources or `wiki/` pages under `cerebruh/`. New knowledge enters the wiki only through cerebruh's own injection-scanned ingest workflow, run from within `cerebruh/`.
- **Exception — lint scaffolding.** `CLAUDE.md` files under `cerebruh/` are agent-context scaffolding, not wiki content, and may be created or edited from any directory to satisfy the lint rules below. Treat them as structural metadata: keep them minimal (typically `@../../template/CLAUDE.md`) and never use them to inject knowledge claims.
- Stay within your own role. Reading shared knowledge does not change what each agent is responsible for.

## Lint

Rules for CLAUDE.md files in this workspace. These exist to keep agent context consistent, discoverable, and low-maintenance.

### Coverage

- CLAUDE.md is required at **context boundaries** — places where an agent's operating rules, role, or domain changes. Concretely: the workspace root, each top-level directory (e.g., `cerebruh/`), and any subdirectory with rules that meaningfully differ from its parent.
- CLAUDE.md is **not** required in every directory. Skip auto-generated dirs (`node_modules/`, `dist/`, `build/`, `.git/`), vendored code, and leaf directories whose purpose is obvious from context.

### Cross-references

- With the exception of this root-level CLAUDE.md, every CLAUDE.md file mentions its parent directory.
- Every CLAUDE.md lists its meaningful children. A child is "meaningful" if it shapes the agent's context or behavior — regardless of file format. Specifically:
   - A subdirectory is meaningful if it either contains its own CLAUDE.md, or holds files the agent is expected to read, update, or treat as authoritative (e.g., ai-sleeve/ holding rebalance snapshots and the investable universe).
   - A file is meaningful if the agent is expected to read, update, or treat it as authoritative (e.g., USER.md, persona/soul files, role definitions).
   - Source code, build artifacts, generated data, and files discoverable through normal task exploration are not considered meaningful.
- Reference cerebruh **only when adding domain-specific routing** (e.g., "for accounting questions, see `cerebruh/wikis/accounting/`"). Do not restate the general cerebruh usage policy — that lives in this root-level CLAUDE.md and is inherited.

### Paths

- All paths in CLAUDE.md and import files are correct (i.e., no broken links). Relative paths resolve relative to the file containing the import, not the working directory.

### Imports

- Imports do not compound. Along any path from a working directory up to the workspace root, a given file must be imported at most once. Never import a file that an ancestor CLAUDE.md already imports. Siblings or cousins may share the same imported file — that does not duplicate content in any single context.