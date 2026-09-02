# Private context example

Copy `AGENTS.example.md` to `.private/AGENTS.md` and replace the synthetic values locally. Copy `RESUME-BULLET-BANK.example.md` to `.private/Resume Bullet Bank.md`, remove the synthetic entries, and populate it only from private source records or candidate confirmation. Create `.private/CLAUDE.md` containing only `@AGENTS.md`, then create `CLAUDE.local.md` in the agent root containing `@.private/AGENTS.md` so Claude Code loads the private context.

The career-dossier publication workflow uses the synthetic contracts in:

- `CAREER-CLAIM-PROVENANCE.example.json`;
- `DOSSIER-PUBLICATION-MANIFEST.example.json`; and
- `DOSSIER-PROPOSAL.example.json`.

Run `.bin/dossier_publication.py --help` for the local initialization, audit, proposal-check, exact-diff review, stale-status, and approval-gated publication commands. The real copies belong only in `.private/`; proposal review never writes tracked content, and publication requires a sealed diff plus the exact approval phrase.

All `.private/` paths are git-ignored. This example directory is public and must remain synthetic.
