# Private context example

Copy `AGENTS.example.md` to `.private/AGENTS.md` and replace the synthetic values locally. Copy `RESUME-BULLET-BANK.example.md` to `.private/Resume Bullet Bank.md`, remove the synthetic entries, and populate it only from private source records or candidate confirmation. Create `.private/CLAUDE.md` containing only `@AGENTS.md`, then create `CLAUDE.local.md` in the agent root containing `@.private/AGENTS.md` so Claude Code loads the private context. These local paths are git-ignored; this example directory is public and must remain synthetic.
