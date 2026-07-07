---
name: synthesis-pass
description: Delta-driven synthesis — mine what changed since the last pass for novel connections, contradictions, and pattern updates; append findings to the synthesis page.
---

# /synthesis-pass

## Purpose

`holistic-health-synthesis.md` proved the wiki can produce novel cross-cutting
patterns (steroid-insensitivity cascade, Xarelto-malabsorption → PE chain), but
synthesis was a one-time manual effort. This skill makes it systemic: every run
mines **only the delta since the last pass** against the full compiled graph,
so insight generation compounds as the wiki grows instead of depending on
someone remembering to look.

This runs daily via `com.life-wiki.synthesis` (06:00, after dream 03:15 and
the leak scan 02:30). The runner `daily-synthesis.sh` is snapshot-gated in
bash — on days with no wiki changes it exits before invoking Claude, so the
daily cadence is effectively "synthesize the same day data lands." The pass
ends with an on-demand mirror sync, so Bernard gets results same-day. Manual
run: `/synthesis-pass` or `bash .claude/scripts/daily-synthesis.sh`.

**Hard rules (same as all health work):** never recommend medication changes,
doses, or diagnoses. Every factual claim cites a wikilink. Uncited inference is
marked `> Hypothesis:`. Contradictions are preserved, never smoothed. This
skill writes only to `wiki/` and `shared/` pages — never `raw/`, never
`ingest/`.

## Workflow

### Step 0 — Establish the window

1. Read `AGENT-HANDOFF.md` (hard rule).
2. Read `wikis/health/wiki/holistic-health-synthesis.md`. The latest dated
   entry in its `## Synthesis Log` section is the last-pass date. If the
   section is missing or empty, use `2026-06-09` (original generation date).

### Step 1 — Build the delta

Collect everything that changed in the window:

- `git log --since="<last-pass-date>" --name-only --pretty=format: -- wikis/ | sort -u`
  — plus `git status --porcelain wikis/` for uncommitted changes.
- New rows in `wikis/sources.md` dated in the window.
- Classify the changed files: new raw sources, new/updated entity pages
  (conditions, medications, biomarkers, providers), new records, new journal
  entries. **Ignore pure-mechanical changes** (frontmatter backfills, PHI
  sweeps, link repairs) — synthesis cares about new facts, not housekeeping.

If the delta contains no substantive new facts (mechanical changes only —
the runner's snapshot gate already filters out fully-idle days), append a
one-line `- YYYY-MM-DD — no substantive delta (mechanical changes only)`
entry to the Synthesis Log and stop. The entry matters: it resets the window
so the next pass doesn't re-scan changes already judged mechanical.

### Step 2 — Pull graph context for the delta

For each changed/new entity page:

- `gbrain graph-query wikis/health/shared/<kind>/<slug> --depth 2` — what does
  this entity now touch that it didn't before?
- `gbrain orphans` once per pass — new pages with no inbound links are
  synthesis targets *and* graph defects; fix the missing links as you go.
- `bash .claude/scripts/wiki-query "<new finding in plain words>"` — semantic
  neighbors that wikilinks don't capture yet.

### Step 3 — Mine the delta (three questions per new fact)

For each substantive new fact in the delta, ask:

1. **Does it touch an existing pattern?** Check against every numbered section
   of the synthesis page. New labs that confirm, extend, or undercut a
   documented pattern get recorded either way — refutation is as valuable as
   confirmation.
2. **Does it contradict anything?** Compare against the claims already on the
   entity pages it touches. For any conflict, follow the
   `.claude/skills/contradiction-review/SKILL.md` workflow: extract both claims with
   dates and source types, rank by source hierarchy, add a
   `> Contradiction:` block to the entity page. Do not resolve — preserve.
3. **Does it complete a chain?** The signature move of the original synthesis:
   two or more previously-unconnected documented facts that, combined with the
   new fact, form a mechanism, timeline, or causal chain no single page states.
   (Pattern: fact A on page X + fact B on page Y + new fact C → chain.)
   Cite every link in the chain; mark the inferential step `> Hypothesis:`.

### Step 4 — Write the findings

1. **Append to the Synthesis Log** (append-only — never rewrite old entries)
   in `holistic-health-synthesis.md`:

   ```markdown
   ### YYYY-MM-DD pass

   **Delta:** N new sources, M entity pages updated (window: <start> → <end>).

   - **Pattern updates:** §3 Xarelto chain — [what changed] [[source]]
   - **New contradictions:** [claim A] [[src-A]] vs [claim B] [[src-B]] — logged on [[entity-page]]
   - **New connections:** [the chain, each step cited]
   - **Watch items:** [things one data point short of a pattern — next pass checks these first]
   ```

2. **Update the compiled zone** (the numbered patterns above the Synthesis
   Log): when a pattern's status genuinely changes (confirmed, refuted,
   extended), edit the section in place with a dated, cited bullet. Promote a
   recurring Synthesis Log finding to a new numbered section once it has ≥2
   independent cited sources.
3. **Cross-link both directions:** any entity page named in a new connection
   gets a wikilink to the synthesis page in its body (and the synthesis page's
   `## Entity Links` section gains any newly-involved entities). Findings that
   GBrain can't traverse to don't exist for Bernard.
4. Bump `date_last_updated` in the synthesis page frontmatter.

### Step 5 — Reindex and mirror

```bash
gbrain import ~/life-wiki/wikis/ --no-embed && gbrain embed --stale && gbrain extract links --source db
bash .claude/scripts/vps-mirror-sync.sh   # health domain changed — same-day freshness for Bernard
```

(The mirror sync is gated on a fresh clean leak-scan; if the gate refuses,
report it — do not bypass.)

### Step 6 — Close out

- Update `AGENT-HANDOFF.md` Last Session (domains touched, pattern count,
  contradictions logged).
- Report a summary: delta size, patterns updated, contradictions found, new
  connections, watch items carried forward.

## Why the loop compounds

Each pass converts raw deltas into compiled, cited, linked truth. The next
pass mines its delta against that *enriched* graph — so a lab result that
meant nothing in isolation in week 1 can complete a chain in week 6 because
the intermediate links now exist as traversable pages. Watch items carried in
the Synthesis Log give each pass a hypothesis list to test against new data,
which is what makes this a flywheel rather than a repeated cold start.
