---
description: End-of-session retrospective — ask "is there anything here worth saving?"
argument-hint: "[optional: where I diverged from what you wanted]"
---

# /retro

A self-improvement retrospective on this session. Not a decision log, not a summary — a Scrum-style retro asking one question:

> **Is there anything here worth saving so the user can one-shot the prompt next time?**

## Input

`$ARGUMENTS` may contain a free-text note from the user describing where your default behavior diverged from what they actually wanted. Example: *"I recommended SSE, user went with polling because the infra team standardized on it."*

- **If `$ARGUMENTS` is present:** focus the retro on that specific divergence. Still scan the rest of the session for other candidates, but treat the named gap as the primary one.
- **If `$ARGUMENTS` is empty:** scan the session yourself for moments where the user corrected, overrode, rephrased, or pushed back on your default — and use judgment to identify candidates.

## The bar for saving anything

Memory files, rule files, and CLAUDE.md files cost tokens on **every future session**. The bar is high. A candidate is worth saving only if it is **both**:

1. **Likely to recur** — the situation will come up again, not a one-off.
2. **Something you'd plausibly get wrong again** without the nudge — i.e. your default behavior doesn't already cover it.

If a candidate fails either test, drop it. Writing nothing is the correct outcome more often than not. Resist the urge to manufacture lessons.

## Process

1. **Identify candidates.** Either from `$ARGUMENTS` or by scanning the session. Be honest — most sessions have zero or one real candidate, not five.
2. **For each candidate, propose the smallest fix that closes the gap.** Usually one of:
   - A one-line addition to an Auto Memory file (user/project/reference) — for cross-session preferences and facts.
   - An instruction in a rules file (`<project>/.claude/rules/<rule>.md`). This keeps instructions modular and easier for teams to maintain. If practical, scope the rule to a specific file path.
   - A sentence in a `CLAUDE.md` — for rules that should bind every future session in a specific directory. Prefer the narrowest scope (project subdirectory > project root > workspace root).
   - **Shared knowledge into `cerebruh/`** — for durable, reusable knowledge (facts, research, domain references) that other agents across The Borg would benefit from, and that isn't a behavioral rule, a cross-session preference, or directory-scoped binding (so it doesn't fit CLAUDE.md, a rule, or memory). Never write `cerebruh/` wiki content (`raw/` or `wiki/`) directly — it is read-only. Instead, stage the knowledge as a new descriptively-named `.md` source file in `cerebruh/ingest/`, then tell the user to ingest it from the cerebruh folder (i.e. ask cerebruh to run its ingest workflow). Staging the file does **not** file it into the wiki; cerebruh's injection scan and human-curated ingest step do that.
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
