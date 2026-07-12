#!/usr/bin/env python3
"""Render a phone-readable chart PNG from long-format tracking CSV data.

Built for exports like Guava Health (one row per observation:
type,datetime,name,value,...) but works on any long-format CSV.

Usage:
    make_chart.py --csv FILE --title "May symptoms" [options]

Options:
    --kind line|bar      line = daily values over time (default)
                         bar  = horizontal bars of per-series averages
    --where COL=VALUE    row filter, repeatable (e.g. --where type=Symptom)
    --date-col datetime  --name-col name  --value-col value
    --names "A,B,C"      explicit series (case-insensitive); default: --top by mean
    --top N              max series on one chart (default 6 — more is unreadable)
    --start / --end      ISO date range filter
    --smooth N           N-day rolling mean overlay (line charts)
    --out PATH           output path (default: auto-named in briefs/)

Prints the absolute PNG path. Attach it in your reply on its own line as:
    MEDIA: /path/to/chart.png
"""
import argparse
import re
import secrets
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = Path.home() / "health-wiki-workspace" / "briefs"

CREAM = "#f4f1ea"   # same warm low-glare palette as the PDF briefs
INK = "#38362f"
MUTED = "#6e6a5f"
PALETTE = ["#2c6e63", "#b3563a", "#4a6fa5", "#8a5fa0", "#c2913a", "#5b8a4a"]


def style():
    plt.rcParams.update({
        "figure.facecolor": CREAM, "axes.facecolor": CREAM,
        "savefig.facecolor": CREAM,
        "text.color": INK, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": MUTED, "axes.linewidth": 0.8,
        "font.size": 14, "axes.titlesize": 19, "axes.titleweight": "bold",
        "axes.titlepad": 16, "legend.fontsize": 13,
        "axes.grid": True, "grid.color": "#dcd7ca", "grid.linewidth": 0.7,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", choices=["line", "bar"], default="line")
    ap.add_argument("--where", action="append", default=[],
                    metavar="COL=VALUE")
    ap.add_argument("--date-col", default="datetime")
    ap.add_argument("--name-col", default="name")
    ap.add_argument("--value-col", default="value")
    ap.add_argument("--names")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--smooth", type=int, default=0)
    ap.add_argument("--out")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    for cond in args.where:
        col, _, val = cond.partition("=")
        df = df[df[col].astype(str).str.strip().str.lower() == val.strip().lower()]

    df = df[[args.date_col, args.name_col, args.value_col]].copy()
    df.columns = ["date", "name", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed",
                                utc=True).dt.tz_localize(None).dt.normalize()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "name", "value"])
    if args.start:
        df = df[df["date"] >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df["date"] <= pd.Timestamp(args.end)]
    if df.empty:
        raise SystemExit("no rows left after filtering — check --where/--start/--end")

    means = df.groupby("name")["value"].mean().sort_values(ascending=False)
    if args.names:
        wanted = [n.strip().lower() for n in args.names.split(",")]
        series = [n for n in means.index if n.lower() in wanted]
        missing = set(wanted) - {s.lower() for s in series}
        if missing:
            print(f"note: not found in data: {', '.join(sorted(missing))}")
    else:
        series = list(means.index[:args.top])
    dropped = len(means) - len(series)

    style()
    daily = df.groupby(["name", "date"])["value"].mean()

    if args.kind == "line":
        fig, ax = plt.subplots(figsize=(11, 6), dpi=200)
        for i, name in enumerate(series[:args.top]):
            s = daily.loc[name].sort_index()
            color = PALETTE[i % len(PALETTE)]
            if args.smooth:
                ax.plot(s.index, s.values, color=color, alpha=0.12, linewidth=0.9)
                s = s.rolling(f"{args.smooth}D").mean()
            ax.plot(s.index, s.values, color=color, linewidth=2.4,
                    marker="o", markersize=3.5,
                    label=f"{name} (avg {means[name]:.1f})")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=9))
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10),
                  ncol=2, frameon=False)
    else:
        show = series if args.names else list(means.index[:max(args.top, 12)])
        fig, ax = plt.subplots(figsize=(11, max(4.0, 0.55 * len(show) + 1.5)), dpi=200)
        vals = means[show][::-1]
        ax.barh(vals.index, vals.values, color=PALETTE[0], height=0.62)
        for y, v in enumerate(vals.values):
            ax.text(v + 0.08, y, f"{v:.1f}", va="center", fontsize=13, color=INK)
        ax.set_xlim(0, max(vals.values) * 1.15)
        dropped = 0

    ax.set_title(args.title)
    note = f"Source: {Path(args.csv).name}"
    if dropped > 0:
        note += f" · top {len(series)} of {len(means)} series shown"
    fig.text(0.01, 0.01, note, fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if args.out:
        out = Path(args.out)
    else:
        OUT_DIR.mkdir(mode=0o700, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", args.title).strip("-")[:40] or "chart"
        out = OUT_DIR / f"{slug}-{date.today():%Y-%m-%d}-{secrets.token_hex(3)}.png"
    fig.savefig(out)
    print(out)


if __name__ == "__main__":
    main()
