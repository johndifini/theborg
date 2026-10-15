# Private context example

Copy `AGENTS.example.md` to `.private/AGENTS.md` and `WATCH-LOG.example.md` to `.private/WATCH-LOG.md`, then replace the synthetic values locally. Create `.private/CLAUDE.md` containing only `@AGENTS.md`. Then create `CLAUDE.local.md` in the agent root containing `@.private/AGENTS.md`, so Claude Code loads the private context. Both local paths are git-ignored. This example directory is public and must remain synthetic.
