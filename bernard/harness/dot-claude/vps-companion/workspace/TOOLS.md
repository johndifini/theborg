# Tools & Environment

## Wiki mirror (read-only)

- Content: `~/health-wiki-mirror/wikis/` — health, shared entities
  (providers/conditions/medications/biomarkers/questions), journal entries.
- Freshness: `~/health-wiki-mirror/MIRROR-STATUS.md` (last sync time).
- Search with `rg` (installed), grep, ls, cat. Page titles live in the first
  `# heading`; frontmatter `aliases` help find entities. **Never bulk-search
  `wikis/health/clinical/raw/`** — it is 94% of the mirror by size; answer
  from the compiled pages (`shared/`, `wiki/`, `clinical/wiki/`) first.
- Never edit anything under the mirror — it is mount-enforced read-only.
- **Be fast.** Plan the 2–4 commands you need before running anything; don't
  probe for tools. What exists: rg, grep/find, and the venv at
  `~/health-wiki-workspace/.venv` (matplotlib, pandas, fpdf2, Pillow,
  markdown). One targeted search beats five exploratory ones.

## Answer formats — don't default to PDF

- **Plain chat text**: anything up to ~8 sentences. Most answers.
- **Chart PNG attached directly**: {{PERSON_NAME}} asks for a graph/trend.
- **PDF brief**: genuinely multi-section content — a table, a timeline,
  "the full picture".

## Charts — make_chart.py is the ONLY chart path

Never hand-roll matplotlib/PIL code, never hand-assemble PDF or image bytes,
never re-derive stats with ad-hoc csv scripts. One command does it:

```bash
~/health-wiki-workspace/.venv/bin/python ~/health-wiki-workspace/skills/publish-brief/make_chart.py \
  --csv ~/health-wiki-mirror/wikis/health/personal-tracking/raw/2025-08-25-2026-05-31-guava-health-symptom-tracking.csv \
  --where type=Symptoms --start 2026-05-01 --end 2026-05-31 \
  --kind bar --title "May 2026 symptom averages"
```

It prints a PNG path under `briefs/` — attach that with `MEDIA:`. Options:
`--kind line --smooth 7` for trends, `--names "A,B"` for exact series,
default top 6 by average (max 6 lines per chart; make a second chart for more).
The symptom-tracking CSV above is the Guava Health export (long format:
`type,datetime,...,name,value`); other tracking CSVs in the same folder work too.

## Daily symptom score & trends

Three artifacts, all under `~/health-wiki-mirror/wikis/health/personal-tracking/wiki/`:

- `daily-symptom-score.md` — compiled plain-language summary + 35-day table +
  monthly trends. Read this first for any score/trend question; don't
  recompute anything by hand.
- `daily-symptom-scores.csv` — full machine-readable history, same folder.
  Columns: `date,burden,score,n_symptoms,n_entries,energy,mood,top_drivers,flags`.
- `charts/score-30d.png` and `charts/score-12m.png` — pre-rendered, same folder.

**Always quote the page's freshness line** ("**Data through YYYY-MM-DD**…")
whenever you give a score. If that date is more than 7 days old, say so
*prominently, before the number* — the score is stale, not current.

**Explain the score every time, not just the digit**: 0–100, **higher =
worse**, it's a percentile against *her own* trailing year — "a 72 means that
day was worse than 72% of her days over the past year." Never compare it to
anyone else or to a clinical cutoff.

**Narrate descriptively only** — trend words (improving / worsening / stable,
straight from the page's 7-day-vs-30-day direction) and named top drivers.
Never interpret clinically, never suggest a cause, no advice, no dosing —
you're describing what the tracker recorded, not diagnosing it.

- WhatsApp does NOT render markdown tables — never reply with one. For
  multi-day listings use short lines instead: `Mon Jun 29 — 56 (brain fog 9,
  fatigue 8)`.
- "Past month" / "past year" questions → answer from the page's 35-day table
  or 12-month table respectively. Don't re-derive stats from the CSV when the
  page already has the number.
- Scheduled summaries → daily: attach `charts/score-card.png` (the at-a-glance card); weekly deep-dive: attach `charts/score-30d.png` via the
  media reply mechanism (see Delivery, below), alongside the text.
- Ad-hoc custom-range chart requests ("show me March") aren't covered by the
  two pre-rendered PNGs, and `make_chart.py` doesn't read the score CSV — for
  these, render directly in the exec sandbox from `daily-symptom-scores.csv`
  with `python3` + `matplotlib`. **matplotlib is pending curator install in
  the sandbox image** — if `import matplotlib` fails, say custom-range charts
  aren't available yet and fall back to the numbers from the table.
- Log every score exchange like any other answer — see "Logging every
  answer" below (use `outcome: chart` when you attached a PNG).

## publish-brief — PDF for multi-section answers

Write the content as markdown to a temp file, then:

```bash
~/health-wiki-workspace/.venv/bin/python ~/health-wiki-workspace/skills/publish-brief/make_brief_pdf.py /tmp/brief.md --title "Title for the page"
```

It prints a PDF path under `briefs/`. To include a chart in a PDF, generate
the PNG first and put `![title](/absolute/path.png)` on its own line in the
markdown — it renders full page width.

## Delivery — MEDIA paths must be under briefs/

Send any attachment by putting this on its own line in your reply (one warm
sentence of context above it):

```
MEDIA: /home/lashaws/health-wiki-workspace/briefs/<printed-filename>
```

**Your shell runs in a sandbox container. `/tmp` is container-local — the
messaging layer cannot see it, so `MEDIA: /tmp/...` silently fails to
deliver.** Both renderer scripts already output to `briefs/`; never override
that with `--out /tmp/...`. (Temp *inputs* like brief markdown in /tmp are
fine.) Files in `briefs/` are cleaned up after ~30 days; regenerate on
request. Nothing is hosted online — attachments travel inside WhatsApp only.

## Logging every answer — REQUIRED (do it as part of replying)

**Every** substantive answer — **DM or group, same rule, no exception** — must be
recorded. Treat writing the log line as part of sending your reply, not an
optional afterthought: do it every time you answer a real question (skip only
pure greetings/chit-chat). This is the learning loop that improves the record —
if you don't log it, the curator never learns what was asked.

Append ONE line to `~/health-wiki-workspace/bernard-conversation-log.md` in
exactly this shape (the Mac-side learner parses it literally):

`- YYYY-MM-DD HH:MM — asker — Q: <question, one clause> — pages: <page titles used, comma-sep, or none> — outcome: answered|partial|gap|chart|brief — feedback: <their reaction, or none>`

- `asker`: who asked (in a group, the specific person).
- `outcome`: `answered` (fully from the wiki) | `partial` | `gap` (couldn't —
  also append a `wiki-question-inbox.md` line) | `chart` | `brief` (you produced an attachment).
- `feedback`: any explicit reaction, short and verbatim-ish ("that's not
  right", "thanks, exactly", "also compare X") — the most valuable field.
- One line only. No PII beyond the pseudonymized record; if unsure, write the
  topic, not the detail.

## Writable files (everything else is read-only — especially the mirror)

- `~/health-wiki-workspace/wiki-question-inbox.md` — append one line per gap you hit.
- `~/health-wiki-workspace/bernard-conversation-log.md` — append one line per
  substantive exchange (format + rule above in "Logging every answer"). This is the
  learning-loop signal; both this and the inbox are pulled back by the sync.
- `~/health-wiki-workspace/memory/` and `MEMORY.md` — your session-continuity
  notes; write here freely (including pre-compaction memory flushes).
- `/tmp` (scratch inputs only) and `~/health-wiki-workspace/briefs/`
  (all attachment outputs).

Never write anywhere under `~/health-wiki-mirror/` — it is overwritten by sync.
