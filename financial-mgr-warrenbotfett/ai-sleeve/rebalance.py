#!/usr/bin/env python3
"""AI sleeve rebalance: STEP 2-5 and STEP 8 of the monthly prompt, reproducibly.

The prompt `financial-mgr-warrenbotfett/.claude/scheduled/financial-mgr-warrenbotfett-ai-sleeve-monthly.prompt`
owns the method; this script is its executable form. It:

* parses `ai-sleeve/universe.md` (Tunables, `categories`, `soft_excludes`);
* fetches each active candidate's cap from its stockanalysis.com page with one
  fixed extractor (the `marketCap:"<n><T|B|M>"` field of the embedded page data,
  fetched with plain curl and its default user agent), twice per ticker, and
  flags any ticker whose two fetches disagree by more than 10%;
* runs the STEP 4 constraint-aware selection and STEP 5 floor weighting;
* writes the STEP 8 history CSV plus a companion `.caps.tsv` with every
  candidate's cap, so a run can be replayed exactly with `--caps`.

Standard library only. The JSON result goes to stdout. Exit codes:
  0  basket computed (and CSV written if `--write-history`)
  2  halt per the prompt (over-constrained category, no valid swap, weight-sum
     mismatch, malformed universe.md); nothing is written
  3  caps need review (a fetch failed or two fetches disagree by >10%);
     nothing is written. Cross-check the ticker and re-run with `--manual-cap`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_DIR = SCRIPT_DIR.parent
DEFAULT_UNIVERSE = SCRIPT_DIR / "universe.md"
DEFAULT_HISTORY_DIR = AGENT_DIR / ".private" / "ai-sleeve" / "history"

DISAGREEMENT_PCT = 10.0
WEIGHT_SUM_TOLERANCE = 0.05
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*$")
CAP_RE = re.compile(r'marketCap:"([0-9]+(?:\.[0-9]+)?)([TBM])"')
UNIT_TO_B = {"T": 1000.0, "B": 1.0, "M": 0.001}
SOURCES = (
    ("stockanalysis.com/stocks", "https://stockanalysis.com/stocks/{t}/"),
    ("stockanalysis.com/etf", "https://stockanalysis.com/etf/{t}/"),
)
MANUAL_SOURCE = "companiesmarketcap.com"
CSV_COLUMNS = [
    "date", "run_type", "rank", "ticker", "weight_pct", "status", "forced",
    "cap_b", "categories", "cap_source", "fetched_at",
]
CAPS_COLUMNS = ["ticker", "cap_b", "cap_raw", "cap_source", "fetched_at"]


class Halt(Exception):
    """A STEP 2/4/5 halt condition. `details` is reported verbatim."""

    def __init__(self, reason: str, details=None):
        super().__init__(reason)
        self.reason = reason
        self.details = details


# --------------------------------------------------------------------------
# STEP 2: universe.md
# --------------------------------------------------------------------------

def _fenced_block(text: str, tag: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "```" + tag:
            body = []
            for inner in lines[i + 1:]:
                if inner.strip() == "```":
                    return "\n".join(body)
                if "```" in inner:
                    raise Halt(
                        f"universe.md: a code fence is glued onto a line inside the `{tag}` block",
                        inner,
                    )
                body.append(inner)
            raise Halt(f"universe.md: `{tag}` block has no closing fence")
    raise Halt(f"universe.md: no ```{tag} block")


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def _scalar(value: str):
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        return float(value)


def _parse_tunables(block: str) -> dict:
    tun: dict = {"ticker_floors": {}}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i])
        i += 1
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "ticker_floors":
            floors = {}
            if value.startswith("{"):
                inner = value.strip("{} ")
                for pair in filter(None, (p.strip() for p in inner.split(","))):
                    t, _, v = pair.partition(":")
                    floors[t.strip()] = float(v)
            else:
                while i < len(lines) and lines[i].startswith((" ", "\t")):
                    sub = _strip_comment(lines[i]).strip()
                    i += 1
                    if sub:
                        t, _, v = sub.partition(":")
                        floors[t.strip()] = float(v)
            tun["ticker_floors"] = floors
        elif value:
            tun[key] = _scalar(value)
    for required in ("basket_size", "floor_pct"):
        if required not in tun:
            raise Halt(f"universe.md: Tunables block lacks `{required}`")
    tun["basket_size"] = int(tun["basket_size"])
    tun["floor_pct"] = float(tun["floor_pct"])
    return tun


def _parse_categories(block: str) -> list[dict]:
    cats: list[dict] = []
    current = None
    for raw in block.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            name = line.strip().rstrip(":")
            current = {"name": name, "members": [], "min": 0}
            cats.append(current)
            continue
        if current is None:
            raise Halt("universe.md: categories block starts with an indented line", raw)
        key, _, value = line.strip().partition(":")
        key, value = key.strip(), value.strip()
        if key == "members":
            members = [m.strip() for m in value.strip("[] ").split(",") if m.strip()]
            bad = [m for m in members if not TICKER_RE.match(m)]
            if bad:
                raise Halt(f"universe.md: bad ticker(s) in category {current['name']}", bad)
            current["members"] = members
        elif key == "min":
            current["min"] = int(value)
        else:
            raise Halt(f"universe.md: unknown key `{key}` in category {current['name']}")
    names = [c["name"] for c in cats]
    if len(set(names)) != len(names):
        raise Halt("universe.md: duplicate category name", names)
    return cats


def _parse_soft_excludes(block: str) -> list[dict]:
    out = []
    for raw in block.splitlines():
        if not raw.strip():
            continue
        head, _, note = raw.partition("#")
        ticker = head.strip()
        if not TICKER_RE.match(ticker):
            raise Halt("universe.md: soft_excludes line does not start with one ticker", raw)
        out.append({"ticker": ticker, "note": note.strip()})
    return out


def parse_universe(text: str) -> dict:
    tunables = _parse_tunables(_fenced_block(text, "yaml"))
    categories = _parse_categories(_fenced_block(text, "categories"))
    soft = _parse_soft_excludes(_fenced_block(text, "soft_excludes"))
    excluded = {s["ticker"] for s in soft}
    for c in categories:
        c["effective_members"] = [m for m in c["members"] if m not in excluded]
    candidates: list[str] = []
    for c in categories:
        for m in c["effective_members"]:
            if m not in candidates:
                candidates.append(m)
    return {
        "basket_size": tunables["basket_size"],
        "floor_pct": tunables["floor_pct"],
        "ticker_floors": tunables["ticker_floors"],
        "categories": categories,
        "soft_excludes": soft,
        "candidates": candidates,
    }


def validate_universe(u: dict) -> None:
    over = [
        {"category": c["name"], "min": c["min"], "effective_members": c["effective_members"]}
        for c in u["categories"]
        if len(c["effective_members"]) < c["min"]
    ]
    if over:
        raise Halt("category over-constrained by soft_excludes", over)
    total_min = sum(c["min"] for c in u["categories"])
    if total_min > u["basket_size"]:
        raise Halt(
            "sum of category mins exceeds basket_size",
            {"sum_min": total_min, "basket_size": u["basket_size"]},
        )
    if len(u["candidates"]) < u["basket_size"]:
        raise Halt(
            "fewer active candidates than basket_size",
            {"candidates": len(u["candidates"]), "basket_size": u["basket_size"]},
        )


# --------------------------------------------------------------------------
# STEP 3: caps
# --------------------------------------------------------------------------

def parse_cap(raw: str) -> float:
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([TBM])\s*", raw)
    if not m:
        raise ValueError(f"cap {raw!r} is not <n><T|B|M>")
    return float(m.group(1)) * UNIT_TO_B[m.group(2)]


def extract_cap(html: str):
    """Return the page's own `marketCap:"<n><T|B|M>"` value, or None.

    A page whose embedded data holds more than one distinct marketCap value is
    ambiguous (it may be quoting a peer), so it yields None rather than a guess.
    """
    found = {m.group(1) + m.group(2) for m in CAP_RE.finditer(html)}
    if len(found) != 1:
        return None
    return found.pop()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def curl_fetch(url: str, timeout: int = 30):
    """Fetch with plain curl (its default user agent). Returns (status, body)."""
    proc = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", str(timeout), "-w", "\n%{http_code}", url],
        capture_output=True, text=True, errors="replace",
    )
    body, _, code = proc.stdout.rpartition("\n")
    return (int(code) if code.isdigit() else 0), body


def fetch_one(ticker: str, fetch=curl_fetch, save_dir: Path | None = None, tag: str = ""):
    """One observation of `ticker`'s cap: first source in SOURCES that yields it."""
    errors = []
    for source, url_tmpl in SOURCES:
        url = url_tmpl.format(t=ticker.lower())
        fetched_at = _now()
        try:
            status, body = fetch(url)
        except Exception as exc:  # network failure: try the next source
            errors.append(f"{url}: {exc}")
            continue
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            name = f"{ticker.lower()}{tag}.{source.split('/')[-1]}.html"
            (save_dir / name).write_text(body)
        raw = extract_cap(body) if status == 200 else None
        if raw is None:
            errors.append(f"{url}: HTTP {status}, no single marketCap field")
            continue
        return {"raw": raw, "cap_b": parse_cap(raw), "source": source,
                "fetched_at": fetched_at, "url": url}
    return {"error": "; ".join(errors)}


def fetch_caps(tickers, fetch=curl_fetch, passes: int = 2, pause: float = 2.0,
               workers: int = 4, save_dir: Path | None = None):
    """Fetch every ticker `passes` times. Returns (caps, flags).

    caps[t] = the first pass's observation, with every pass under `observations`.
    flags lists fetch failures and >10% disagreements between passes.
    """
    observations: dict[str, list] = {t: [] for t in tickers}
    for p in range(passes):
        if p:
            time.sleep(pause)
        tag = f".pass{p + 1}" if passes > 1 else ""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda t: fetch_one(t, fetch, save_dir, tag), tickers))
        for t, r in zip(tickers, results):
            observations[t].append(r)
    caps, flags = {}, []
    for t in tickers:
        good = [o for o in observations[t] if "error" not in o]
        if not good:
            flags.append({"ticker": t, "kind": "fetch_failed",
                          "detail": observations[t][-1]["error"]})
            continue
        lo, hi = min(o["cap_b"] for o in good), max(o["cap_b"] for o in good)
        if lo <= 0 or (hi - lo) / lo * 100 > DISAGREEMENT_PCT:
            flags.append({"ticker": t, "kind": "fetches_disagree",
                          "detail": [{"raw": o["raw"], "source": o["source"],
                                      "fetched_at": o["fetched_at"]} for o in good]})
        caps[t] = dict(good[0], observations=len(good))
    return caps, flags


def load_caps_file(path: Path) -> dict:
    """Read a replay file: the `.caps.tsv` this script writes, or a bare
    `TICKER<TAB>cap` table where cap is `<n><T|B|M>` or a number of $B."""
    caps = {}
    with path.open() as fh:
        for row in fh:
            row = row.rstrip("\n")
            if not row.strip() or row.startswith("#") or row.startswith("ticker\t"):
                continue
            cols = row.split("\t")
            ticker = cols[0].strip()
            if len(cols) >= 5:  # our .caps.tsv: ticker cap_b cap_raw source fetched_at
                caps[ticker] = {"cap_b": float(cols[1]), "raw": cols[2],
                                "source": cols[3], "fetched_at": cols[4]}
                continue
            value = cols[1].strip()
            cap_b = parse_cap(value) if value[-1:] in UNIT_TO_B else float(value)
            caps[ticker] = {"cap_b": cap_b, "raw": value,
                            "source": cols[2].strip() if len(cols) > 2 and cols[2].strip()
                            else "stockanalysis.com/stocks",
                            "fetched_at": cols[3].strip() if len(cols) > 3 else "replay"}
    return caps


def caps_from_html_dir(tickers, html_dir: Path):
    """Replay the fixed extractor over saved pages named `<ticker_lower>.html`."""
    caps, flags = {}, []
    for t in tickers:
        page = html_dir / f"{t.lower()}.html"
        if not page.exists():
            flags.append({"ticker": t, "kind": "fetch_failed", "detail": f"no {page}"})
            continue
        raw = extract_cap(page.read_text(errors="replace"))
        if raw is None:
            flags.append({"ticker": t, "kind": "fetch_failed",
                          "detail": f"{page}: no single marketCap field"})
            continue
        mtime = dt.datetime.fromtimestamp(page.stat().st_mtime, dt.timezone.utc)
        caps[t] = {"raw": raw, "cap_b": parse_cap(raw), "source": "stockanalysis.com/stocks",
                   "fetched_at": mtime.replace(microsecond=0).isoformat()}
    return caps, flags


def apply_manual_caps(caps: dict, flags: list, manual: list[str]):
    """`--manual-cap TICKER=<n><T|B|M>`: a cross-checked value (companiesmarketcap.com
    fallback) that replaces the fetch and clears that ticker's flags."""
    for item in manual:
        ticker, _, raw = item.partition("=")
        ticker = ticker.strip().upper()
        caps[ticker] = {"raw": raw.strip(), "cap_b": parse_cap(raw), "source": MANUAL_SOURCE,
                        "fetched_at": _now(), "manual": True}
        flags[:] = [f for f in flags if f["ticker"] != ticker]


# --------------------------------------------------------------------------
# STEP 4: selection
# --------------------------------------------------------------------------

def _rank_key(caps):
    return lambda t: (-caps[t]["cap_b"], t)


def select_basket(u: dict, caps: dict) -> dict:
    n = u["basket_size"]
    cats = [c for c in u["categories"] if c["min"] > 0]
    ranked = sorted(u["candidates"], key=_rank_key(caps))
    provisional = ranked[:n]
    basket = list(provisional)
    swaps = []

    def count(c):
        return sum(1 for m in c["effective_members"] if m in basket)

    def unsatisfied():
        return [c for c in cats if count(c) < c["min"]]

    guard = 0
    while True:
        short = unsatisfied()
        if not short:
            break
        guard += 1
        if guard > len(u["candidates"]) * len(cats) + 1:
            raise Halt("selection did not converge", [c["name"] for c in short])
        cat = short[0]
        missing = sorted((m for m in cat["effective_members"] if m not in basket),
                         key=_rank_key(caps))
        incoming = missing[0]
        short_members = {m for c in short for m in c["effective_members"]}
        victim = None
        for t in sorted(basket, key=_rank_key(caps), reverse=True):  # lowest cap first
            if t in short_members:
                continue
            if any(t in c["effective_members"] and count(c) - 1 < c["min"] for c in cats):
                continue
            victim = t
            break
        if victim is None:
            raise Halt("no valid swap resolves the category minimums", {
                "unsatisfied": [{"category": c["name"], "min": c["min"],
                                 "present": [m for m in c["effective_members"] if m in basket],
                                 "missing": [m for m in c["effective_members"] if m not in basket]}
                                for c in short],
                "competing_for_slot": incoming,
            })
        basket.remove(victim)
        basket.append(incoming)
        swaps.append({"category": cat["name"], "in": incoming, "out": victim})

    basket.sort(key=_rank_key(caps))
    forced = [t for t in basket if t not in provisional]
    raw_rank = {t: i + 1 for i, t in enumerate(ranked)}
    return {"basket": basket, "provisional": provisional, "forced": forced,
            "swaps": swaps, "raw_rank": raw_rank}


# --------------------------------------------------------------------------
# STEP 5: weights
# --------------------------------------------------------------------------

def compute_weights(u: dict, caps: dict, basket: list[str]) -> dict:
    total = sum(caps[t]["cap_b"] for t in basket)
    raw = {t: caps[t]["cap_b"] / total * 100 for t in basket}
    floor = {t: float(u["ticker_floors"].get(t, u["floor_pct"])) for t in basket}
    floored = [t for t in basket if raw[t] < floor[t]]
    free = [t for t in basket if t not in floored]
    free_pool = 100 - sum(floor[t] for t in floored)
    free_cap = sum(caps[t]["cap_b"] for t in free)
    weights = {t: floor[t] for t in floored}
    for t in free:
        weights[t] = caps[t]["cap_b"] / free_cap * free_pool
    rounded = {t: round(w, 2) for t, w in weights.items()}
    total_w = sum(rounded.values())
    if abs(total_w - 100) > WEIGHT_SUM_TOLERANCE:
        raise Halt("final weights do not sum to 100 ± 0.05",
                   {"sum": round(total_w, 4), "weights": rounded})
    status = {t: ("floored" if t in floored else "free") for t in basket}
    return {"weights": rounded, "raw_weights": {t: round(w, 4) for t, w in raw.items()},
            "status": status, "weight_sum": round(total_w, 4)}


# --------------------------------------------------------------------------
# Assembly and STEP 8 output
# --------------------------------------------------------------------------

def categories_of(u: dict, ticker: str) -> list[str]:
    return [c["name"] for c in u["categories"] if ticker in c["members"]]


def build_result(u: dict, caps: dict) -> dict:
    missing = [t for t in u["candidates"] if t not in caps]
    if missing:
        raise Halt("no cap for active candidate(s)", missing)
    sel = select_basket(u, caps)
    w = compute_weights(u, caps, sel["basket"])
    rows = []
    for rank, t in enumerate(sel["basket"], 1):
        rows.append({
            "rank": rank, "ticker": t, "weight_pct": w["weights"][t],
            "status": w["status"][t], "forced": t in sel["forced"],
            "raw_cap_rank": sel["raw_rank"][t], "cap_b": round(caps[t]["cap_b"], 2),
            "cap_raw": caps[t]["raw"], "categories": categories_of(u, t),
            "cap_source": caps[t]["source"], "fetched_at": caps[t]["fetched_at"],
        })
    cat_status = []
    for c in u["categories"]:
        present = [t for t in sel["basket"] if t in c["effective_members"]]
        cat_status.append({"category": c["name"], "min": c["min"], "present": present,
                           "forced": [t for t in present if t in sel["forced"]]})
    return {
        "basket_size": u["basket_size"], "floor_pct": u["floor_pct"],
        "ticker_floors": u["ticker_floors"], "basket": rows,
        "weight_sum": w["weight_sum"], "swaps": sel["swaps"],
        "provisional_top_n": sel["provisional"], "categories": cat_status,
        "soft_excludes": u["soft_excludes"],
        "candidates": [{"ticker": t, "cap_b": round(caps[t]["cap_b"], 2),
                        "cap_raw": caps[t]["raw"], "cap_source": caps[t]["source"],
                        "fetched_at": caps[t]["fetched_at"],
                        "raw_cap_rank": sel["raw_rank"][t]}
                       for t in sorted(u["candidates"], key=_rank_key(caps))],
    }


def write_history(result: dict, history_dir: Path, date: str, run_type: str) -> dict:
    history_dir.mkdir(parents=True, exist_ok=True)
    csv_path = history_dir / f"{date}-{run_type}.csv"
    caps_path = history_dir / f"{date}-{run_type}.caps.tsv"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CSV_COLUMNS)
        for r in result["basket"]:
            w.writerow([date, run_type, r["rank"], r["ticker"], f"{r['weight_pct']:.2f}",
                        r["status"], "true" if r["forced"] else "false",
                        f"{r['cap_b']:.2f}", ";".join(r["categories"]),
                        r["cap_source"], r["fetched_at"]])
    with caps_path.open("w") as fh:
        fh.write("\t".join(CAPS_COLUMNS) + "\n")
        for c in result["candidates"]:
            fh.write("\t".join([c["ticker"], f"{c['cap_b']:.4f}",
                                c["cap_raw"], c["cap_source"], c["fetched_at"]]) + "\n")
    return {"csv": str(csv_path), "caps": str(caps_path)}


def format_text(result: dict) -> str:
    lines = [f"{'rank':>4}  {'ticker':<6} {'weight%':>8}  {'status':<8} {'cap $B':>10}  source"]
    for r in result["basket"]:
        name = r["ticker"] + ("*" if r["forced"] else "")
        lines.append(f"{r['rank']:>4}  {name:<6} {r['weight_pct']:>8.2f}  {r['status']:<8} "
                     f"{r['cap_b']:>10.2f}  {r['cap_source']}")
    lines.append(f"sum {result['weight_sum']:.2f}")
    for c in result["categories"]:
        if c["min"]:
            lines.append(f"{c['category']} (min {c['min']}): "
                         + ", ".join(t + ("*" if t in c["forced"] else "") for t in c["present"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--caps", type=Path, help="replay caps from a .caps.tsv (no network)")
    src.add_argument("--html-dir", type=Path,
                     help="replay the extractor over saved <ticker>.html pages (no network)")
    ap.add_argument("--save-html", type=Path, help="keep every fetched page in this directory")
    ap.add_argument("--manual-cap", action="append", default=[], metavar="TICKER=<n><T|B|M>",
                    help="cross-checked cap (companiesmarketcap.com) replacing a flagged fetch")
    ap.add_argument("--passes", type=int, default=2, help="fetches per ticker (default 2)")
    ap.add_argument("--write-history", action="store_true", help="write the STEP 8 CSV")
    ap.add_argument("--run-type", choices=("scheduled", "interactive"), default="interactive")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    ap.add_argument("--text", action="store_true", help="print a table to stderr as well")
    args = ap.parse_args(argv)

    out: dict = {"date": args.date, "run_type": args.run_type, "universe": str(args.universe)}
    try:
        u = parse_universe(args.universe.read_text())
        validate_universe(u)
        if args.caps:
            caps, flags = load_caps_file(args.caps), []
        elif args.html_dir:
            caps, flags = caps_from_html_dir(u["candidates"], args.html_dir)
        else:
            caps, flags = fetch_caps(u["candidates"], passes=max(1, args.passes),
                                     save_dir=args.save_html)
        apply_manual_caps(caps, flags, args.manual_cap)
        if flags:
            out.update(status="needs_review", flags=flags,
                       caps={t: {k: v for k, v in c.items()} for t, c in caps.items()})
            print(json.dumps(out, indent=2))
            return 3
        result = build_result(u, caps)
    except Halt as h:
        out.update(status="halt", reason=h.reason, details=h.details)
        print(json.dumps(out, indent=2))
        return 2
    out.update(status="ok", **result)
    if args.write_history:
        out["history_files"] = write_history(result, args.history_dir, args.date, args.run_type)
    print(json.dumps(out, indent=2))
    if args.text:
        print(format_text(result), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
