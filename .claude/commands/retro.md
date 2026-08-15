---
description: Retrospective — "is there anything here worth saving?" This session by default; `/retro sessions` for the last week's transcripts.
argument-hint: "[optional: where I diverged from what you wanted | 'sessions [window]']"
---

# /retro

A self-improvement retrospective. Not a decision log, not a summary — a Scrum-style retro asking one question:

> **Is there anything here worth saving so the user can one-shot the prompt next time?**

## Scope — this session, or many

Two scopes, same question and same bar. Dispatch on the **first word** of `$ARGUMENTS`:

- **`$ARGUMENTS` begins with the literal token `sessions`** → the multi-session retro,
  described in [Multi-session scope](#multi-session-scope) below. Anything after that
  token is the window (e.g. `sessions last 14 days`).
- **Anything else, including empty** → this session. Follow the rest of this document.

Match the token literally and only in first position. A free-text note that merely
*mentions* sessions or a date range ("we spent the whole session on this", "like last
week") is a correction note, not a scope switch — `/wrap` seeds `$ARGUMENTS` that way,
and misreading it would silently kick off a multi-day transcript scan.

## Input

Everything from here to [Multi-session scope](#multi-session-scope) is the single-session
retro. `$ARGUMENTS` may contain a free-text note from the user describing where your
default behavior diverged from what they actually wanted. Example: *"I recommended SSE, user went with polling because the infra team standardized on it."*

- **If `$ARGUMENTS` is present:** focus the retro on that specific divergence. Still scan the rest of the session for other candidates, but treat the named gap as the primary one.
- **If `$ARGUMENTS` is empty:** scan the session yourself for moments where the user corrected, overrode, rephrased, or pushed back on your default — and use judgment to identify candidates.

## The bar for saving anything

Memory files, rule files, and AGENTS.md files cost tokens on **every future session**. The bar is high. A candidate is worth saving only if it is **both**:

1. **Likely to recur** — the situation will come up again, not a one-off.
2. **Something you'd plausibly get wrong again** without the nudge — i.e. your default behavior doesn't already cover it.

If a candidate fails either test, drop it. Writing nothing is the correct outcome more often than not. Resist the urge to manufacture lessons.

## Process

1. **Identify candidates.** Either from `$ARGUMENTS` or by scanning the session. Be honest — most sessions have zero or one real candidate, not five.
2. **For each candidate, propose the smallest fix that closes the gap.** Usually one of:
   - A one-line addition to an Auto Memory file (user/project/reference) — for cross-session preferences and facts.
   - An instruction in a rules file (`<project>/.claude/rules/<rule>.md`). This keeps instructions modular and easier for teams to maintain. If practical, scope the rule to a specific file path.
   - A sentence in a `AGENTS.md` — for rules that should bind every future session in a specific directory. Prefer the narrowest scope (project subdirectory > project root > workspace root).
   - **Shared knowledge into `cerebruh/`** — for durable, reusable knowledge (facts, research, domain references) that other agents across The Borg would benefit from, and that isn't a behavioral rule, a cross-session preference, or directory-scoped binding (so it doesn't fit AGENTS.md, a rule, or memory). Never write `cerebruh/` wiki content (`raw/` or `wiki/`) directly — it is read-only. Instead, stage the knowledge as a new descriptively-named `.md` source file in `cerebruh/ingest/`, then tell the user to ingest it from the cerebruh folder (i.e. ask cerebruh to run its ingest workflow). Staging the file does **not** file it into the wiki; cerebruh's injection scan and human-curated ingest step do that.
   - **Nothing** — if the lesson isn't general enough, say so explicitly and move on.
3. **Ask per-item before writing.** No auto-pick. Show the user:
   - What you observed (the gap)
   - The proposed change (exact text, exact file path)
   - Why you think it clears the bar
   Then wait for approval, rejection, or edits.
4. **Apply approved changes only.** Don't batch silently.

## Output shape

Start with a one-line verdict: either *"Nothing worth saving from this session."* or *"N candidate(s) worth your review."* Then list each candidate as:

- **Gap:** what your default did vs. what the user wanted
- **Proposed change:** file path + exact text to add/modify
- **Why it clears the bar:** one sentence on recurrence + likelihood-of-recurrence-error

Keep the whole output short. This is a retro, not a report.

## Multi-session scope

Reached only via `/retro sessions [window]`. Same logic as the launchd job
`com.theborg.c4po-retro`, executed here in the session instead of on a schedule — no
duplicated instructions.

Read and follow the instructions in
`<workspace-root>/c4po/.claude/scheduled/c4po-retro.prompt`. Treat every occurrence of
`${BORG_ROOT}` in that file as the repo root — the output of
`git rev-parse --show-toplevel` (the `theborg` directory).

The prompt's phases are named (GATE, WINDOW, HARVEST, OUTPUT, RECORD STATE). Apply these
overrides for interactive invocation, referenced by phase name:

1. Skip the **GATE** phase entirely — do not check the weekly state file. An interactive
   run should always execute, regardless of whether the scheduled job already ran this
   week.
2. In the **WINDOW** phase — do not read the state file for the boundary. Use the last 7
   days, or the window named after the `sessions` token if one is given (e.g.
   `/retro sessions last 14 days`). Still produce the prompt's full per-harness
   raw/excluded/eligible manifest and cross-harness deduplication; this override changes
   only the time boundary.
3. In the **OUTPUT** phase — do NOT pipe to `notify-email.sh`. Output the full digest into
   this session, including the non-sensitive scan manifest (say "nothing cleared the bar"
   when that is the outcome). For cerebruh
   candidates, do NOT auto-stage into `cerebruh/ingest/`; instead show the proposed source
   file (path + content) and ask before staging it. (Rule / AGENTS.md / skill candidates
   remain propose-only, exactly as in the scheduled run.)
4. Skip the **RECORD STATE** phase entirely — do not write the state file. An interactive
   run must not move the harvest-window boundary for the next scheduled run.
