#!/usr/bin/env python3
"""self_interrogate.py — recommendation ②: the wiki asks itself questions.

Generates probing questions by detecting structural gaps in the graph, then emits
inbox lines (deduped against the existing inbox + archive). The curator triages
them like any other inbox item; the mechanical ones can later be auto-fixed.

Detectors (low-false-positive, deterministic):
  D1 isolated-condition : condition page with no entity links in OR out
  D2 untreated-med      : medication referenced by no condition/biomarker and
                          referencing none (what is it for?)
  D3 missing-entity     : a slug used in entry frontmatter with no entity page
                          (the highest-value, most actionable gap)
  D5 timeline-gap       : a stretch > GAP_DAYS with no dated entry (completeness)

Output one inbox line per gap:  - DATE — question — what's missing [self-interrogate]
Default prints candidates; the wrapper handles dedup + append.
"""
import argparse, os, re, glob, sys, datetime

ENTITY_CATS = ["conditions", "medications", "biomarkers", "providers"]
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
GAP_DAYS = 45


def split_fm(text):
    if text.startswith("---"):
        e = text.find("\n---", 3)
        if e != -1:
            nl = text.find("\n", e + 1)
            return text[3:e], (text[nl + 1:] if nl != -1 else "")
    return "", text


def list_field(fm, field):
    out = []
    m = re.search(rf"^{field}:\s*\[(.*?)\]\s*$", fm, re.MULTILINE)
    if m:
        return [p.strip().strip("'\"") for p in m.group(1).split(",") if p.strip()]
    m = re.search(rf"^{field}:\s*$", fm, re.MULTILINE)
    if m:
        for line in fm[m.end():].splitlines():
            if re.match(r"^\s*-\s+", line):
                out.append(re.sub(r"^\s*-\s+", "", line).strip().strip("'\""))
            elif line.strip() and not line.startswith(" "):
                break
    return out


def body_entity_links(body, entity_keys):
    refs = set()
    for m in LINK_RE.finditer(body):
        t = m.group(1).split("|")[0].split("#")[0].strip().lstrip("./")
        if t.endswith(".md"):
            t = t[:-3]
        if t in entity_keys:
            refs.add(t)
    return refs


def collect(wiki_root):
    shared = os.path.join(wiki_root, "wikis/health/shared")
    entries_dir = os.path.join(wiki_root, "wikis/journal/wiki/entries")
    entity_path = {}
    for cat in ENTITY_CATS:
        for f in glob.glob(os.path.join(shared, cat, "*.md")):
            entity_path["wikis/health/shared/%s/%s" % (cat, os.path.basename(f)[:-3])] = f
    keys = set(entity_path)

    out_links = {k: set() for k in keys}   # entity -> entities it links to
    in_links = {k: set() for k in keys}    # entity -> entities linking to it
    # links among entity pages
    for k, f in entity_path.items():
        _, body = split_fm(open(f, encoding="utf-8", errors="ignore").read())
        for t in body_entity_links(body, keys):
            if t != k:
                out_links[k].add(t)
                in_links[t].add(k)

    # entry references + frontmatter slugs (for missing-entity + timeline)
    fm_slug_refs = {}  # "cat/slug" -> count
    entry_dates = []
    for ef in glob.glob(os.path.join(entries_dir, "*.md")):
        txt = open(ef, encoding="utf-8", errors="ignore").read()
        fm, body = split_fm(txt)
        m = DATE_RE.search(os.path.basename(ef)) or DATE_RE.search(fm)
        if m:
            entry_dates.append(m.group(1))
        for cat, field in [("conditions", "conditions"), ("medications", "medications"),
                           ("providers", "providers")]:
            for slug in list_field(fm, field):
                key = "%s/%s" % (cat, slug)
                full = "wikis/health/shared/%s" % key
                if full not in keys:
                    fm_slug_refs[key] = fm_slug_refs.get(key, 0) + 1
        # entries linking to entities count as inbound for D1/D2 isolation purposes
        for t in body_entity_links(body, keys):
            in_links[t].add("entry")
    return entity_path, out_links, in_links, fm_slug_refs, sorted(set(entry_dates))


def load_profile(path):
    """Read calibration-profile.tsv -> {category: (real, noise, precision)}."""
    prof = {}
    if path and os.path.exists(path):
        for i, line in enumerate(open(path, encoding="utf-8", errors="ignore")):
            if i == 0 or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) >= 4:
                try:
                    prof[f[0]] = (int(f[1]), int(f[2]), float(f[3]))
                except ValueError:
                    pass
    return prof


def annotate(missing, category, prof):
    """Append a historical-precision note for a self-interrogate sub-category."""
    key = f"self-interrogate:{category}"
    if key in prof:
        real, noise, prec = prof[key]
        if real + noise >= 4:
            return f"{missing} (history: {real}/{real + noise} of this category confirmed real)"
    return missing


def detect(wiki_root, today, prof=None):
    prof = prof or {}
    entity_path, out_links, in_links, fm_slug_refs, dates = collect(wiki_root)
    q = []  # (question, missing)

    for k in sorted(entity_path):
        cat = k.split("/")[-2]
        name = k.split("/")[-1]
        ext_in = in_links[k]
        if cat == "conditions" and not out_links[k] and not ext_in:
            q.append((f"How does the condition '{name}' connect to the rest of the picture?",
                      annotate(f"{k} has no entity links in or out — fully isolated in the graph",
                               "isolated-condition", prof)))
        if cat == "medications" and not out_links[k] and not (ext_in - {"entry"}):
            q.append((f"What condition(s) is the medication '{name}' treating?",
                      annotate(f"{k} links to no condition/biomarker and none link to it",
                               "untreated-med", prof)))

    for key, n in sorted(fm_slug_refs.items(), key=lambda x: -x[1]):
        q.append((f"Should there be an entity page for '{key.split('/')[-1]}'?",
                  annotate(f"slug '{key}' is used in {n} entry frontmatter block(s) but no page exists "
                           f"at wikis/health/shared/{key}", "missing-entity", prof)))

    # D5 timeline gaps
    ds = [datetime.date.fromisoformat(d) for d in dates]
    for a, b in zip(ds, ds[1:]):
        gap = (b - a).days
        if gap > GAP_DAYS:
            q.append((f"Is the timeline complete between {a} and {b}?",
                      annotate(f"{gap}-day stretch with no dated entry — possible missing "
                               f"appointments/records", "timeline-gap", prof)))
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument("--today", default="")  # for deterministic tests
    ap.add_argument("--profile", default="")  # calibration-profile.tsv (rec ⑤ feedback)
    a = ap.parse_args()
    if not os.path.isdir(a.wiki_root):
        print("bad --wiki-root", file=sys.stderr)
        return 2
    today = a.today or datetime.date.today().isoformat()
    prof = load_profile(a.profile)
    for question, missing in detect(a.wiki_root, today, prof):
        print(f"- {today} — {question} — {missing} [self-interrogate]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
