---
description: Ask a few targeted clarifying questions about a request before doing any work on it.
argument-hint: "[the request to clarify; otherwise the most recent request in this session]"
---

# /clarify

Settle the decisions that would change the outcome of a request *before* any work
starts, so the work is done once.

The request is `$ARGUMENTS`. When it is empty, use the user's most recent request
in this session. If there is none, ask what they want done and stop.

## 1. Find what is actually ambiguous

- You may make a few cheap, read-only lookups (read a file, list a directory,
  grep) so you do not ask what the workspace already answers. Make no edits, run
  nothing with side effects, and start no part of the work itself.
- A question earns a place only if its answer changes what you build or do:
  scope, the owning agent or repository, the deliverable's form, a constraint, or
  what "done" means. Skip anything with a conventional default; state the
  default instead.
- Do not ask for permission to proceed, and do not ask about style the workspace
  already settles (design goes through `jony-vibe/`; formats follow
  `AGENTS.md`).

## 2. Ask

- Ask **two to four** questions, most consequential first. One is fine when only
  one thing is unclear.
- Make each question concrete and answerable at a glance, with two to four
  options where the choices are discrete. Put your recommended option first and
  mark it `(Recommended)`.
- In Claude Code, use the `AskUserQuestion` tool. Elsewhere, write a numbered
  list of questions with lettered options, then stop and wait for the reply.
- After the questions, list in one or two lines the assumptions you will make
  for everything you did not ask about.

If nothing material is ambiguous, ask nothing: say so in one line, list your
assumptions, and proceed as in step 3.

## 3. Then do the work

Once answered, restate the request as a short brief (two to four lines, with the
answers folded in) and carry it out. If an answer opens a new, decisive
ambiguity, ask once more; do not run a second round for minor points.
