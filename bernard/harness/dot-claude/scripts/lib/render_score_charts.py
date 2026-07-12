#!/usr/bin/env python3
"""render_score_charts.py — static PNG charts from daily-symptom-scores.csv.

Renders three phone-legible, DARK low-glare images for WhatsApp delivery:
  charts/score-card.png — daily card: word-first severity band, 30-day tinted
                          history with 30-day average, toughest-symptoms
                          leaderboard with week-over-week movement
  charts/score-30d.png  — daily score bars + 7-day average line, last 30 days
  charts/score-12m.png  — monthly mean line with best-worst day band

Score semantics: 0-100, HIGHER = WORSE, percentile vs the patient's own trailing
year. Deterministic; no model, no network. Idempotent: skips when PNGs are newer
than the scores CSV. Dark palette follows the house dataviz reference instance;
severity-band colors are redundant with position/labels (never color-alone).
"""

import argparse
import csv
import os
import sys
from datetime import date, timedelta

import daily_score as ds

# Dark palette (dataviz reference instance, dark mode — low-glare)
SURFACE = "#1a1a19"
INK_PRIMARY = "#f5f4ef"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRID = "#2c2c2a"
BASELINE = "#383835"
BLUE_LINE = "#6da7ec"
BLUE_BAR = "#35577e"
BLUE_FILL = "#24344a"

# Severity bands: ordered, labeled — color is a redundant channel
BANDS = [
    (0, 20, "Gentle", "#3f7d5a"),
    (20, 40, "Manageable", "#7d7f45"),
    (40, 60, "Hard", "#a8843b"),
    (60, 80, "Very hard", "#b06a3d"),
    (80, 101, "Severe", "#ad4b40"),
]


def band_of(score):
    for lo, hi, label, color in BANDS:
        if lo <= score < hi:
            return label, color
    return BANDS[-1][2], BANDS[-1][3]


def load_scores(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                y, m, d = r["date"].split("-")
                day = date(int(y), int(m), int(d))
            except (ValueError, KeyError):
                continue
            score = int(r["score"]) if r.get("score") else None
            rows.append((day, score))
    return rows


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_MUTED, labelsize=11, length=0)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])


def title_block(fig, title, subtitle):
    fig.text(0.06, 0.94, title, fontsize=16, fontweight="bold", color=INK_PRIMARY)
    fig.text(0.06, 0.885, subtitle, fontsize=11.5, color=INK_SECONDARY)


def weekly_leaderboard(days, latest, top_n=5):
    """Per-symptom mean of day-max: trailing 7 days vs the 7 before.
    Returns [(name, cur, delta_or_None)] sorted worst-first."""
    def wmean(name, lo_off, hi_off):
        vals = [days[d]["symptoms"][name]
                for d in days
                if latest - timedelta(days=hi_off) <= d <= latest - timedelta(days=lo_off)
                and name in days[d]["symptoms"]]
        return sum(vals) / len(vals) if vals else None

    names = set()
    for d in days:
        if latest - timedelta(days=6) <= d <= latest:
            names.update(days[d]["symptoms"])
    rows = []
    for name in names:
        cur = wmean(name, 0, 6)
        prev = wmean(name, 7, 13)
        if cur is not None:
            rows.append((name, cur, (cur - prev) if prev is not None else None))
    rows.sort(key=lambda r: -r[1])
    return rows[:top_n]


def render_card(plt, scored, days, out_path):
    by_date = dict(scored)
    latest = max(d for d, _ in scored)
    score = by_date[latest]
    blabel, bcolor = band_of(score)

    m7 = [by_date[latest - timedelta(days=i)] for i in range(7)
          if by_date.get(latest - timedelta(days=i)) is not None]
    m30 = [by_date[latest - timedelta(days=i)] for i in range(30)
           if by_date.get(latest - timedelta(days=i)) is not None]
    a7 = sum(m7) / len(m7) if m7 else None
    a30 = sum(m30) / len(m30) if m30 else None
    if a7 is None or a30 is None:
        direction = "not enough data to compare"
    elif a7 - a30 >= 5:
        direction = "getting worse"
    elif a7 - a30 <= -5:
        direction = "improving"
    else:
        direction = "holding steady"

    fig = plt.figure(figsize=(6, 7.5), dpi=180)
    fig.patch.set_facecolor(SURFACE)

    # header
    fig.text(0.07, 0.955, "Daily symptom score", fontsize=17,
             fontweight="bold", color=INK_PRIMARY)
    fig.text(0.07, 0.925, latest.strftime("%A, %B %-d"), fontsize=12.5,
             color=INK_SECONDARY)

    # word-first verdict + number
    fig.text(0.07, 0.845, "A %s day" % blabel.lower(), fontsize=30,
             fontweight="bold", color=INK_PRIMARY)
    fig.text(0.07, 0.808, "score %d / 100 · this week is %s "
             "(7-day avg %s vs 30-day %s)"
             % (score, direction,
                "%d" % round(a7) if a7 is not None else "—",
                "%d" % round(a30) if a30 is not None else "—"),
             fontsize=11.5, color=INK_SECONDARY)

    # severity band scale with marker
    axb = fig.add_axes([0.07, 0.735, 0.86, 0.030])
    axb.set_facecolor(SURFACE)
    for lo, hi, label, color in BANDS:
        axb.barh(0, hi - lo - 1.2, left=lo + 0.6, height=1.0,
                 color=color, linewidth=0)
        axb.text((lo + hi) / 2, -1.35, label, ha="center", va="top",
                 fontsize=9.5, color=INK_MUTED, transform=axb.transData)
    axb.scatter([score], [1.05], marker="v", s=110, color=INK_PRIMARY,
                zorder=5, clip_on=False)
    axb.set_xlim(0, 100)
    axb.set_ylim(-0.5, 0.5)
    axb.axis("off")

    # 30-day full-width history, severity-tinted, 30-day average line
    fig.text(0.07, 0.630, "The last 30 days", fontsize=13.5,
             fontweight="bold", color=INK_PRIMARY)
    fig.text(0.07, 0.604, "one bar per day · taller and warmer = harder"
             " · line = 30-day average (%s)"
             % ("%d" % round(a30) if a30 is not None else "—"),
             fontsize=10.5, color=INK_MUTED)
    axh = fig.add_axes([0.07, 0.435, 0.86, 0.155])
    axh.set_facecolor(SURFACE)
    days30 = [latest - timedelta(days=i) for i in range(29, -1, -1)]
    for i, d in enumerate(days30):
        v = by_date.get(d)
        if v is not None:
            axh.bar(i, v, width=0.72, color=band_of(v)[1], zorder=2)
    if a30 is not None:
        axh.axhline(a30, color=INK_MUTED, linewidth=1, zorder=3)
    axh.annotate("%d" % score, (29, score), xytext=(0, 3),
                 textcoords="offset points", ha="center",
                 fontsize=10, fontweight="bold", color=INK_PRIMARY)
    axh.set_ylim(0, 112)
    axh.set_xlim(-0.7, 29.7)
    for side in axh.spines.values():
        side.set_visible(False)
    ticks = [0, 14, 29]
    axh.set_xticks(ticks)
    axh.set_xticklabels([days30[t].strftime("%b %-d") for t in ticks])
    axh.tick_params(colors=INK_MUTED, labelsize=9.5, length=0)
    axh.set_yticks([])

    # toughest symptoms this week, worst-first, with movement words
    fig.text(0.07, 0.360, "Toughest symptoms this week", fontsize=13.5,
             fontweight="bold", color=INK_PRIMARY)
    fig.text(0.07, 0.334, "average of each day's worst rating · 0–10",
             fontsize=10.5, color=INK_MUTED)
    board = weekly_leaderboard(days, latest)
    axd = fig.add_axes([0.34, 0.085, 0.42, 0.225])
    axd.set_facecolor(SURFACE)
    n = len(board)
    for row, (name, cur, delta) in enumerate(board):
        y = n - 1 - row
        axd.barh(y, cur, height=0.55, color=band_of(cur * 10)[1], zorder=2)
        if delta is None:
            move = "new"
        elif delta >= 0.5:
            move = "up %.1f" % delta
        elif delta <= -0.5:
            move = "down %.1f" % abs(delta)
        else:
            move = "steady"
        axd.text(10.4, y, "%.1f" % cur, va="center", fontsize=11.5,
                 fontweight="bold", color=INK_PRIMARY)
        axd.text(12.3, y, move, va="center", fontsize=10.5,
                 color=INK_SECONDARY)
        yfrac = 0.085 + 0.225 * ((y + 0.5) / max(n, 1))
        fig.text(0.315, yfrac, name, fontsize=11.5, color=INK_PRIMARY,
                 ha="right", va="center")
    axd.set_xlim(0, 14.6)
    axd.set_ylim(-0.55, max(n - 0.45, 0.55))
    axd.axis("off")

    fig.text(0.07, 0.032, "Data through %s · scored against her own past year"
             % latest.strftime("%b %-d, %Y"), fontsize=10, color=INK_MUTED)

    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def rolling_mean(day, by_date, span=7):
    vals = [by_date[day - timedelta(days=i)] for i in range(span)
            if by_date.get(day - timedelta(days=i)) is not None]
    return sum(vals) / len(vals) if vals else None


def render_30d(plt, scored, out_path):
    by_date = dict(scored)
    latest = max(d for d, _ in scored)
    days = [latest - timedelta(days=i) for i in range(29, -1, -1)]
    xs = list(range(len(days)))
    bars = [by_date.get(d) for d in days]
    roll = [rolling_mean(d, by_date) for d in days]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.80, bottom=0.14)
    style_axes(ax)

    for x, b in zip(xs, bars):
        if b is not None:
            ax.bar(x, b, width=0.72, color=BLUE_BAR, zorder=2)
    rx = [x for x, v in zip(xs, roll) if v is not None]
    ry = [v for v in roll if v is not None]
    ax.plot(rx, ry, color=BLUE_LINE, linewidth=2, zorder=4,
            solid_capstyle="round")
    if rx:
        ax.annotate("7-day avg %d" % round(ry[-1]), (rx[-1], ry[-1]),
                    xytext=(-2, 10), textcoords="offset points", ha="right",
                    fontsize=11, fontweight="bold", color=INK_PRIMARY)
    last_scored = [(x, b) for x, b in zip(xs, bars) if b is not None]
    if last_scored:
        x, b = last_scored[-1]
        ax.annotate("%d" % b, (x, b), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=10.5, color=INK_SECONDARY)
    ticks = [i for i, d in enumerate(days) if d.weekday() == 0]
    ax.set_xticks(ticks)
    ax.set_xticklabels([days[i].strftime("%b %-d") for i in ticks])
    title_block(fig, "Daily symptom score — last 30 days",
                "0–100, higher = worse · vs her own past year · gaps = days not"
                " logged · data through %s" % latest.strftime("%b %-d, %Y"))
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)


def render_12m(plt, scored, out_path):
    SPARSE = 7
    months = []
    seen = []
    for d, _ in scored:
        ym = (d.year, d.month)
        if ym not in seen:
            seen.append(ym)
    for ym in seen[-12:]:
        vals = [s for d, s in scored if (d.year, d.month) == ym and s is not None]
        if vals:
            months.append((date(ym[0], ym[1], 1),
                           sum(vals) / len(vals), min(vals), max(vals), len(vals)))
    if not months:
        return False
    xs = list(range(len(months)))
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.80, bottom=0.17)
    style_axes(ax)

    ax.fill_between(xs, [m[2] for m in months], [m[3] for m in months],
                    color=BLUE_FILL, zorder=2, linewidth=0)
    ax.plot(xs, [m[1] for m in months], color=BLUE_LINE, linewidth=2, zorder=4)
    full = [(x, m[1]) for x, m in zip(xs, months) if m[4] >= SPARSE]
    sparse = [(x, m[1]) for x, m in zip(xs, months) if m[4] < SPARSE]
    if full:
        ax.scatter([p[0] for p in full], [p[1] for p in full],
                   s=42, color=BLUE_LINE, zorder=5)
    if sparse:
        ax.scatter([p[0] for p in sparse], [p[1] for p in sparse], s=42,
                   facecolor=SURFACE, edgecolor=BLUE_LINE, linewidth=2, zorder=5)
    ax.annotate("monthly average", (xs[-1], months[-1][1]),
                xytext=(-4, 12), textcoords="offset points", ha="right",
                fontsize=11, fontweight="bold", color=INK_PRIMARY)
    ax.annotate("band: best to worst day", (xs[0], months[0][3]),
                xytext=(0, 8), textcoords="offset points",
                fontsize=10.5, color=INK_SECONDARY)
    labels = []
    for i, m in enumerate(months):
        lab = m[0].strftime("%b")
        if i == 0 or m[0].month == 1:
            lab = m[0].strftime("%b '%y")
        if m[4] < SPARSE:
            lab += "*"
        labels.append(lab)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    if sparse:
        fig.text(0.06, 0.035, "* fewer than %d days logged that month — "
                 "read with caution" % SPARSE, fontsize=10, color=INK_MUTED)
    title_block(fig, "Symptom score by month — last 12 months",
                "0–100, higher = worse · monthly average of daily scores"
                " · vs her own past year")
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument("--scores-csv")
    ap.add_argument("--out-dir")
    ap.add_argument("--apply", action="store_true", help="write PNGs (default: dry-run)")
    args = ap.parse_args()

    base = os.path.join(args.wiki_root, "wikis/health/personal-tracking/wiki")
    scores_csv = args.scores_csv or os.path.join(base, "daily-symptom-scores.csv")
    out_dir = args.out_dir or os.path.join(base, "charts")
    if not os.path.exists(scores_csv):
        print("charts: no scores CSV at %s — nothing to render" % scores_csv)
        return 0
    outs = [os.path.join(out_dir, n)
            for n in ("score-30d.png", "score-12m.png", "score-card.png")]

    src_mtime = os.path.getmtime(scores_csv)
    if all(os.path.exists(o) and os.path.getmtime(o) >= src_mtime for o in outs):
        print("charts: changed: 0 (PNGs newer than scores CSV)")
        return 0

    rows = load_scores(scores_csv)
    scored = [(d, s) for d, s in rows if s is not None]
    if not scored:
        print("charts: no scored days yet — nothing to render")
        return 0

    if not args.apply:
        print("[dry-run] would render %s from %d scored days"
              % (", ".join(outs), len(scored)))
        return 0

    # symptom-level data for the leaderboard, from the raw Guava export
    raw_csv = ds.find_latest_csv(args.wiki_root)
    days = {}
    if raw_csv:
        days, _ = ds.compute_days(ds.load_rows(raw_csv))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Helvetica Neue", "Arial", "DejaVu Sans"]

    os.makedirs(out_dir, exist_ok=True)
    render_30d(plt, scored, outs[0])
    ok12 = render_12m(plt, scored, outs[1])
    render_card(plt, scored, days, outs[2])
    print("charts APPLIED: %s%s + %s"
          % (outs[0], (" + " + outs[1]) if ok12 else "", outs[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
