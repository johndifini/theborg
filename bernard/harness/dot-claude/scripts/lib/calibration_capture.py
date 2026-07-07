#!/usr/bin/env python3
"""calibration_capture.py — recommendation ⑤: learn from curator confirmations.

Every triaged inbox item is a labeled example. When the curator archives a line
they append an outcome tag:
    [done YYYY-MM-DD → target]      -> the question/gap was REAL (true positive)
    [dismissed YYYY-MM-DD: reason]  -> it was noise            (false positive)
This reads inbox-archive.md, computes per-source and per-category precision
(real / (real+noise)) plus median latency, and emits:
  - a machine profile (TSV) the loops can consult
  - tuning hints when a category's precision is low (so a noisy detector gets
    tightened instead of repeatedly crying wolf)

Source tag = the bracket tag on the line ([self-interrogate], [cross-model],
[eval], [bernard], or 'manual' if none). Sub-category for self-interrogate is
inferred from the question wording (timeline-gap / isolated-condition /
untreated-med / missing-entity).
"""
import argparse, os, re, sys, statistics

DONE_RE = re.compile(r"\[done\s+(\d{4}-\d{2}-\d{2})", re.I)
DISMISS_RE = re.compile(r"\[dismiss(?:ed)?\s+(\d{4}-\d{2}-\d{2})", re.I)
TAG_RE = re.compile(r"\[(self-interrogate|cross-model|eval|bernard)\]", re.I)
ASK_DATE_RE = re.compile(r"^-\s+(\d{4}-\d{2}-\d{2})")
PREC_THRESHOLD = 0.34  # below this, a category is mostly noise -> hint to tighten


def categorize(line):
    tag = TAG_RE.search(line)
    src = tag.group(1).lower() if tag else "manual"
    sub = ""
    if src == "self-interrogate":
        low = line.lower()
        if "timeline complete" in low:
            sub = "timeline-gap"
        elif "isolated" in low or "connect to the rest" in low:
            sub = "isolated-condition"
        elif "treating" in low:
            sub = "untreated-med"
        elif "entity page for" in low or "no page exists" in low:
            sub = "missing-entity"
    return src, sub


def days_between(a, b):
    import datetime
    try:
        return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except Exception:
        return None


def analyze(archive_path):
    rows = {}  # key -> {"real":n,"noise":n,"lat":[...]}
    if not os.path.exists(archive_path):
        return rows
    for line in open(archive_path, encoding="utf-8", errors="ignore"):
        if not line.lstrip().startswith("- "):
            continue
        done = DONE_RE.search(line)
        dism = DISMISS_RE.search(line)
        if not (done or dism):
            continue  # still-pending or unlabeled archive line
        src, sub = categorize(line)
        for key in {src, (f"{src}:{sub}" if sub else src)}:
            r = rows.setdefault(key, {"real": 0, "noise": 0, "lat": []})
            if done:
                r["real"] += 1
                ask = ASK_DATE_RE.match(line.strip())
                if ask:
                    d = days_between(ask.group(1), done.group(1))
                    if d is not None and d >= 0:
                        r["lat"].append(d)
            else:
                r["noise"] += 1
    return rows


def render(rows):
    tsv = ["source\treal\tnoise\tprecision\tmedian_latency_days"]
    hints = []
    for key in sorted(rows):
        r = rows[key]
        tot = r["real"] + r["noise"]
        prec = (r["real"] / tot) if tot else 0.0
        med = (str(int(statistics.median(r["lat"]))) if r["lat"] else "")
        tsv.append(f"{key}\t{r['real']}\t{r['noise']}\t{prec:.2f}\t{med}")
        if tot >= 4 and prec < PREC_THRESHOLD:
            hints.append(f"- {key}: only {r['real']}/{tot} confirmed real "
                         f"(precision {prec:.0%}) — consider tightening this detector.")
    return "\n".join(tsv), hints


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out-tsv", default="")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = analyze(a.archive)
    tsv, hints = render(rows)
    if a.out_tsv and a.apply:
        os.makedirs(os.path.dirname(a.out_tsv) or ".", exist_ok=True)
        open(a.out_tsv, "w").write(tsv + "\n")
    print(tsv)
    if hints:
        print("\nTUNING HINTS:")
        print("\n".join(hints))
    else:
        print("\nTUNING HINTS: none (no category with >=4 samples below precision threshold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
