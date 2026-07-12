#!/usr/bin/env python3
"""Render markdown into a migraine-friendly PDF brief, delivered as a WhatsApp
attachment (no public hosting — replaces the old Funnel link model).

Usage:
    make_brief_pdf.py INPUT.md --title "Page title"
    cat notes.md | make_brief_pdf.py - --title "Page title"

Prints the absolute path of the PDF. Include that path in your reply on its
own line as:  MEDIA: /path/to/file.pdf
"""
import argparse
import html
import re
import secrets
import sys
from datetime import date
from pathlib import Path

OUT_DIR = Path.home() / "health-wiki-workspace" / "briefs"
FONT_DIR = Path(__file__).resolve().parent / "fonts"

CREAM = (244, 241, 234)   # warm low-glare paper
INK = (56, 54, 47)        # soft near-black text
MUTED = (110, 106, 95)

LATIN_FALLBACK = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "•": "-", "µ": "u",
    "μ": "u", "°": " deg", "…": "...", "→": "->",
    "≥": ">=", "≤": "<=", "×": "x",
}


def render_markdown(text: str) -> str:
    try:
        import markdown
        return markdown.markdown(text, extensions=["extra", "sane_lists"],
                                 output_format="html5")
    except ImportError:
        return "<p>%s</p>" % html.escape(text).replace("\n\n", "</p><p>")


def main() -> None:
    from fpdf import FPDF

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="markdown file, or - for stdin")
    ap.add_argument("--title", help="title (default: first # heading)")
    args = ap.parse_args()

    text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()

    title = args.title
    if not title:
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = m.group(1).strip() if m else "Health brief"
    text = re.sub(r"^#\s+%s\s*\n" % re.escape(title), "", text, count=1,
                  flags=re.MULTILINE)

    class Brief(FPDF):
        def header(self):
            self.set_fill_color(*CREAM)
            self.rect(0, 0, self.w, self.h, style="F")

        def footer(self):
            self.set_y(-14)
            self.set_font(family, "", 8.5)
            self.set_text_color(*MUTED)
            self.cell(0, 8, f"{self.page_no()}/{{nb}}", align="C")

    pdf = Brief(format="A4")
    pdf.set_margins(20, 22, 20)
    pdf.set_auto_page_break(True, margin=22)

    sans = FONT_DIR / "DejaVuSans.ttf"
    if sans.is_file():
        family = "DejaVu"
        pdf.add_font(family, "", str(sans))
        pdf.add_font(family, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        pdf.add_font(family, "I", str(FONT_DIR / "DejaVuSans-Oblique.ttf"))
    else:
        family = "helvetica"
        for k, v in LATIN_FALLBACK.items():
            text = text.replace(k, v)
        text = text.encode("latin-1", "replace").decode("latin-1")

    # Standalone image lines (![alt](path)) are pulled out of the markdown and
    # drawn at full content width — write_html would otherwise embed them at
    # their pixel size, which comes out unreadably small on A4.
    img_re = re.compile(r"^[ \t]*!\[([^\]]*)\]\(([^)\s]+)\)[ \t]*$", re.MULTILINE)
    segments = []
    pos = 0
    for m in img_re.finditer(text):
        if text[pos:m.start()].strip():
            segments.append(("md", text[pos:m.start()]))
        segments.append(("img", m.group(2), m.group(1)))
        pos = m.end()
    if text[pos:].strip():
        segments.append(("md", text[pos:]))

    pdf.add_page()
    pdf.set_text_color(*INK)
    pdf.set_font(family, "B", 19)
    pdf.multi_cell(0, 9.5, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(family, "", 9.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 8, date.today().strftime("Prepared %B %-d, %Y · private"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_text_color(*INK)
    pdf.set_font(family, "", 12.5)

    def emit_html(chunk: str) -> None:
        body_html = render_markdown(chunk)
        # Large type + generous leading; fall back to defaults if this fpdf2
        # version lacks tag_styles.
        try:
            from fpdf import FontFace
            pdf.write_html(body_html, tag_styles={
                "h2": FontFace(family=family, emphasis="B", size_pt=15, color=INK),
                "h3": FontFace(family=family, emphasis="B", size_pt=13, color=INK),
                "a": FontFace(family=family, color=(37, 101, 92)),
            })
        except Exception:
            pdf.write_html(body_html)

    for seg in segments:
        if seg[0] == "md":
            emit_html(seg[1])
        else:
            _, path, alt = seg
            if Path(path).is_file():
                pdf.ln(3)
                pdf.image(path, w=pdf.epw)
                pdf.ln(3)
            elif alt:
                emit_html(f"*{alt}*")

    OUT_DIR.mkdir(mode=0o700, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:40] or "brief"
    out = OUT_DIR / f"{slug}-{date.today():%Y-%m-%d}-{secrets.token_hex(3)}.pdf"
    pdf.output(str(out))
    print(out)


if __name__ == "__main__":
    main()
