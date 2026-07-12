#!/usr/bin/env python3
"""bernard_learn.py — distill Bernard's pulled conversation log into wiki work.

Input: the local conversation log pulled from the VPS by vps-mirror-sync.sh
(.claude/inbox/bernard-conversation-log.md). Each line, written by Bernard:

  - YYYY-MM-DD HH:MM — asker — Q: <question> — pages: <titles|none> — outcome: answered|partial|gap|chart|brief — feedback: <text|none>

Outputs (the shell wrapper owns dedup/append, mirroring self_interrogate.py):
  * stdout: candidate question-inbox lines, shape `- [bernard] — <topic> — <detail>`
    so the wrapper can dedup them on the field-2 topic against inbox+archive.
  * --usage-out PATH: (re)writes a usage-profile wiki page summarizing what the
    family actually asks — outcome mix, most-asked topics, open gaps, recent
    feedback. Mirror-visible; steers synthesis priorities + new eval questions.

Deterministic, no model calls. Tolerant of malformed lines (skips them).
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

NEG_FEEDBACK = re.compile(
    r"\b(not right|wrong|incorrect|confus|unclear|doesn'?t|didn'?t|nope|"
    r"that'?s not|no,|outdated|out of date|stale)\b", re.I)
STOPWORDS = set("the a an of to is are was were what when how why who which does "
                "did do for in on at and or her his she he they patient's patient "
                "about with that this it her she's".split())
# Temporal/filler words carry no topic meaning ("what meds NOW" == "meds").
TEMPORAL = set("now currently current today recently lately right taking take "
               "takes still these those latest".split())
# Light synonym folding so common paraphrases cluster (deterministic, no model).
SYNONYMS = {"meds": "medication", "med": "medication", "medications": "medication",
            "meds": "medication", "rx": "medication", "drug": "medication",
            "drugs": "medication", "meds'": "medication",
            "doctor": "provider", "doctors": "provider", "physician": "provider",
            "appt": "appointment", "appts": "appointment", "appointments": "appointment"}


def parse_line(line):
    """Return dict or None. Field-prefix scan (tolerant of missing fields)."""
    if not line.startswith("- "):
        return None
    parts = [p.strip() for p in line[2:].split(" — ")]
    rec = {"date": "", "asker": "", "q": "", "pages": "", "outcome": "", "fb": ""}
    # First two positional-ish fields: timestamp, asker (only if not prefixed).
    lead = []
    for p in parts:
        low = p.lower()
        if low.startswith("q:"):
            rec["q"] = p[2:].strip()
        elif low.startswith("pages:"):
            rec["pages"] = p[6:].strip()
        elif low.startswith("outcome:"):
            rec["outcome"] = p[8:].strip().lower()
        elif low.startswith("feedback:"):
            rec["fb"] = p[9:].strip()
        else:
            lead.append(p)
    if lead:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", lead[0])
        rec["date"] = m.group(1) if m else ""
        if len(lead) > 1:
            rec["asker"] = lead[1]
    if not rec["q"]:
        return None
    return rec


def topic_key(q):
    """Normalize a question to an order-independent grouping key.

    Drops stop/temporal words, folds common synonyms, sorts + dedups the rest so
    paraphrases ("meds now" / "current medications") land on the same key.
    """
    out = set()
    for w in re.findall(r"[a-z0-9']+", q.lower()):
        if w in STOPWORDS or w in TEMPORAL or len(w) <= 2:
            continue
        out.add(SYNONYMS.get(w, w))
    return " ".join(sorted(out)) if out else q.lower().strip()


def truncate(s, n=90):
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--usage-out", default="")
    ap.add_argument("--now", default="")  # YYYY-MM-DD; shell passes date for determinism
    args = ap.parse_args()

    try:
        with open(args.log, encoding="utf-8") as f:
            raw = f.readlines()
    except FileNotFoundError:
        print("bernard-learn: no conversation log yet (Bernard not deployed or "
              "nothing pulled) — nothing to learn.", file=sys.stderr)
        return 0

    recs = [r for r in (parse_line(l.rstrip("\n")) for l in raw) if r]
    if not recs:
        print("bernard-learn: conversation log present but no parseable "
              "exchanges yet.", file=sys.stderr)
        return 0

    outcomes = Counter(r["outcome"] or "unknown" for r in recs)
    topics = defaultdict(list)          # key -> list of recs
    topic_display = {}                  # key -> a representative question
    for r in recs:
        k = topic_key(r["q"])
        topics[k].append(r)
        topic_display.setdefault(k, r["q"])

    dates = sorted(r["date"] for r in recs if r["date"])
    span = f"{dates[0]} → {dates[-1]}" if dates else "unknown window"
    today = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ---- candidate inbox lines (stdout; wrapper dedups on field-2 topic) ------
    seen_topics = set()

    def emit(topic, detail):
        # field-2 = topic (drives dedup); keep ' — ' out of detail.
        print(f"- [bernard] — {truncate(topic)} — {detail}")

    # 1. recurring needs answered poorly (asked >=3x with any gap/partial)
    for k, rs in topics.items():
        if len(rs) >= 3 and any(r["outcome"] in ("gap", "partial") for r in rs):
            emit(topic_display[k],
                 f"asked {len(rs)}x and answered weakly at least once; "
                 f"ensure a strong compiled page exists [recurring need]")
            seen_topics.add(k)

    # 2. each distinct gap/partial topic (not already covered above)
    for k, rs in topics.items():
        if k in seen_topics:
            continue
        weak = [r for r in rs if r["outcome"] in ("gap", "partial")]
        if weak:
            pg = weak[-1]["pages"] or "none"
            emit(topic_display[k],
                 f"Bernard answered '{weak[-1]['outcome']}' (pages: "
                 f"{truncate(pg, 50)}); fill or clarify the record")
            seen_topics.add(k)

    # 3. explicit negative feedback (always worth a look, even if 'answered')
    for r in recs:
        if r["fb"] and NEG_FEEDBACK.search(r["fb"]):
            emit(r["q"],
                 f"user feedback: \"{truncate(r['fb'], 70)}\" "
                 f"({r['date'] or 'undated'}); verify/correct [feedback]")

    # ---- usage profile page (side effect) ------------------------------------
    if args.usage_out:
        total = len(recs)
        lines = []
        lines.append("---")
        lines.append("type: overview")
        lines.append("status: active")
        lines.append("domain: shared")
        lines.append(f"date_created: {today}")
        lines.append(f"date_updated: {today}")
        lines.append("source_paths: []")
        lines.append("confidence: medium")
        lines.append("tags: [bernard, usage, learning-loop, companion, auto-generated]")
        lines.append("aliases: [Bernard usage, what the family asks]")
        lines.append("---")
        lines.append("")
        lines.append("# Bernard — Usage Profile")
        lines.append("")
        lines.append("> **Auto-generated** by `bernard-learn.sh` from the pulled "
                     "conversation log. Do not hand-edit — rerun the job. Steers "
                     "synthesis priorities and golden eval questions. See "
                     "[[wikis/shared/bernard-north-star]].")
        lines.append("")
        lines.append(f"- **Window:** {span} — **{total}** exchange(s) captured")
        lines.append("")
        lines.append("## Outcome distribution")
        lines.append("")
        for oc, n in outcomes.most_common():
            pct = round(100 * n / total)
            lines.append(f"- {oc}: {n} ({pct}%)")
        lines.append("")
        lines.append("## Most-asked topics")
        lines.append("")
        ranked = sorted(topics.items(), key=lambda kv: len(kv[1]), reverse=True)
        for k, rs in ranked[:12]:
            ocs = Counter(r["outcome"] or "?" for r in rs)
            oc_str = ", ".join(f"{o}×{c}" for o, c in ocs.most_common())
            lines.append(f"1. \"{truncate(topic_display[k], 80)}\" — "
                         f"{len(rs)}× ({oc_str})")
        lines.append("")
        gaps = [r for r in recs if r["outcome"] in ("gap", "partial")]
        if gaps:
            lines.append("## Open gaps (asked but not answered well)")
            lines.append("")
            for r in gaps[-15:]:
                lines.append(f"- {r['date'] or '—'}: \"{truncate(r['q'], 80)}\" "
                             f"({r['outcome']})")
            lines.append("")
        fbs = [r for r in recs if r["fb"] and r["fb"].lower() != "none"]
        if fbs:
            lines.append("## Recent explicit feedback")
            lines.append("")
            for r in fbs[-12:]:
                lines.append(f"- {r['date'] or '—'}: \"{truncate(r['fb'], 80)}\" "
                             f"(on: {truncate(r['q'], 50)})")
            lines.append("")
        with open(args.usage_out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"bernard-learn: wrote usage profile ({total} exchanges, "
              f"{len(topics)} distinct topics) -> {args.usage_out}",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
