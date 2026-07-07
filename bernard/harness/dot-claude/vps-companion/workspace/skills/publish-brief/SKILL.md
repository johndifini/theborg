# publish-brief (PDF + charts)

Two renderers, both in `~/health-wiki-workspace/skills/publish-brief/`, both
run with `~/health-wiki-workspace/.venv/bin/python`:

- `make_brief_pdf.py` — markdown → calm, large-type PDF
- `make_chart.py` — tracking CSV → phone-readable chart PNG

Nothing is hosted publicly: attachments travel inside WhatsApp, end-to-end
encrypted, and open with one tap.

## Picking the format — don't default to PDF

- **Plain chat text**: anything up to ~8 sentences, even if it has a couple
  of bullet points. Most answers should be text.
- **Chart PNG, attached directly**: {{PERSON_NAME}} asks for a graph/trend
  and a one-paragraph takeaway covers the rest. A PNG opens instantly in the
  chat — no PDF wrapper.
- **PDF brief**: the answer truly needs structure — a table, 2+ sections, a
  timeline — or {{PERSON_NAME}} asks for "the full picture" / "laid out".

## Charts

1. Generate (long-format CSV; symptom tracking lives at
   `~/health-wiki-mirror/wikis/health/personal-tracking/raw/`):
   ```bash
   ~/health-wiki-workspace/.venv/bin/python ~/health-wiki-workspace/skills/publish-brief/make_chart.py \
     --csv ~/health-wiki-mirror/wikis/health/personal-tracking/raw/2025-08-25-2026-05-31-guava-health-symptom-tracking.csv \
     --where type=Symptoms --start 2026-05-01 --end 2026-05-31 \
     --kind line --smooth 7 --title "Top symptoms — May 2026"
   ```
   It prints the PNG path. `--kind bar` ranks averages; `--names "A,B"`
   picks exact series; default is the top 6 by average (more is unreadable).
2. Never hand-draw charts with PIL or ASCII, never hand-assemble PDF bytes,
   and never re-derive stats with ad-hoc csv scripts — `make_chart.py` is the
   only chart path and `make_brief_pdf.py` the only PDF path.
3. Max 6 lines per chart. For more series, make a second chart rather than
   cramming one.

## Sandbox rule — attachments live in briefs/, never /tmp

Your shell runs in a container. `/tmp` is container-local: the messaging
layer CANNOT see it, so a `MEDIA: /tmp/...` line silently fails to attach.
Both renderers already write to `~/health-wiki-workspace/briefs/` — never
override that with `--out /tmp/...`. (Temp *input* files like brief markdown
in /tmp are fine; only attachment outputs must be under `briefs/`.)

## PDF briefs

1. Write clean markdown to a temp file. Lead with a 2–3 sentence
   plain-language summary; short paragraphs and tables where they help.
   To include a chart, generate the PNG first and reference it on its own
   line — it renders at full page width:
   ```markdown
   ![Top symptoms — May 2026](/home/lashaws/health-wiki-workspace/briefs/<chart>.png)
   ```
2. Run:
   ```bash
   ~/health-wiki-workspace/.venv/bin/python ~/health-wiki-workspace/skills/publish-brief/make_brief_pdf.py /tmp/brief.md --title "Clear, human title"
   ```
   It prints the PDF's path.

## Delivery

Reply with one warm sentence of context, then the attachment reference on
its own line (PNG or PDF):

```
MEDIA: /home/lashaws/health-wiki-workspace/briefs/<printed-filename>
```

## Notes

- Output is styled for migraine days — warm low-glare background, large
  type. Never apologize for formatting.
- Give files clear titles; the filename is visible in the chat.
- Files in `briefs/` are deleted after ~30 days. Regenerate on request.
- Cite wiki page titles inside the brief just as you do in chat.
