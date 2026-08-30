# Media Project Workspace

## Parent

This directory belongs to `../`, the Jony Vibe design and branding agent. Its role, design principles, and repository-routing rules continue to apply here.

## Purpose

Use this directory for standalone media projects that do not belong to an independent repository under `../../repos/`. The tracked files define a public, reusable framework; real project directories are private and git-ignored by default.

## Directory Structure

- `example/` — Synthetic example showing the minimum instruction and project-record structure for a media project.

## Rules

- Start a new standalone media project by copying the structure of `example/` into a descriptively named project directory.
- Keep real project names, briefs, source files, generated assets, and other project-specific details inside their ignored project directories. Do not mention private project directories in tracked documentation.
- Give each project an `AGENTS.md`, an adjacent `CLAUDE.md` compatibility wrapper, and a `README.md` that records its authoritative assets and reproducible prompts.
- Keep operational instructions in `AGENTS.md`; keep project facts, visual specifications, asset manifests, and prompts in `README.md` instead of duplicating them into always-loaded context.
- Preserve approved final assets. Create versioned variants rather than overwriting a selected final unless the user explicitly asks for replacement.
- Store design deliverables for a repository under that repository's `design/` directory, not here.
