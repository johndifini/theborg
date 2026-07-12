#!/usr/bin/env python3
"""Render markdown into a self-contained, migraine-friendly HTML brief.

Writes ~/briefs/<random-token>.html and prints the public URL (served via
Tailscale Funnel). The token is the only access control — never list, index,
or guess-ably name briefs.

Usage:
    publish_brief.py INPUT.md --title "Page title"
    cat notes.md | publish_brief.py - --title "Page title"
"""
import argparse
import html
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import date
from pathlib import Path

BRIEFS_DIR = Path.home() / "briefs"
TEMPLATE = Path(__file__).resolve().parent / "template.html"
CONFIG = Path.home() / ".config" / "publish-brief" / "config"


def render_markdown(text: str) -> str:
    try:
        import markdown
        return markdown.markdown(
            text, extensions=["extra", "sane_lists", "smarty"], output_format="html5"
        )
    except ImportError:
        # Degraded but safe: readable preformatted text inside the styled shell.
        return "<pre style='white-space:pre-wrap'>%s</pre>" % html.escape(text)


def base_url() -> str:
    if os.environ.get("BRIEF_BASE_URL"):
        return os.environ["BRIEF_BASE_URL"].rstrip("/")
    if CONFIG.is_file():
        for line in CONFIG.read_text().splitlines():
            if line.startswith("BRIEF_BASE_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    try:
        status = json.loads(
            subprocess.run(
                ["tailscale", "status", "--json"], capture_output=True, check=True
            ).stdout
        )
        dns = status["Self"]["DNSName"].rstrip(".")
        return f"https://{dns}/briefs"
    except Exception:
        return "file://" + str(BRIEFS_DIR)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="markdown file, or - for stdin")
    ap.add_argument("--title", help="page title (default: first # heading)")
    args = ap.parse_args()

    text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()

    title = args.title
    if not title:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = m.group(1).strip() if m else "Health brief"
    # Drop a leading H1 that duplicates the template's title slot.
    text = re.sub(r"^#\s+%s\s*\n" % re.escape(title), "", text, count=1, flags=re.MULTILINE)

    page = (
        TEMPLATE.read_text()
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{DATE}}", date.today().strftime("%B %-d, %Y"))
        .replace("{{CONTENT}}", render_markdown(text))
    )

    BRIEFS_DIR.mkdir(mode=0o700, exist_ok=True)
    out = BRIEFS_DIR / f"{secrets.token_hex(16)}.html"
    out.write_text(page)
    out.chmod(0o644)

    print(f"{base_url()}/{out.name}")


if __name__ == "__main__":
    main()
