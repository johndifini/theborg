#!/usr/bin/env python3
"""Build a multipart notification email from the Markdown body on stdin.

This is deliberately a small, dependency-free renderer, not a general Markdown
engine. It supports the constructs emitted by Borg jobs: ATX headings, unordered
and ordered lists, pipe tables (with a Markdown separator row), links, emphasis,
inline code, fenced/indented code, block quotes, horizontal rules, and paragraphs.
Raw HTML is escaped. Nested lists, images, footnotes, task lists, and arbitrary
Markdown extensions are intentionally left as readable text.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate
from typing import Optional
from urllib.parse import urlsplit


FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace"
TEXT = "#202124"
MUTED = "#5f6368"
BORDER = "#dadce0"
SURFACE = "#f8f9fa"


def safe_url(value: str) -> Optional[str]:
    """Allow only useful email-link schemes; unsafe links remain plain text."""
    if any(ord(char) < 32 for char in value):
        return None
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return None
    return html.escape(value, quote=True)


INLINE_TOKEN = re.compile(
    r"(`[^`\n]+`|\[[^\]\n]+\]\([^\s)]+\)|\*\*[^*\n]+\*\*|(?<!\*)\*[^*\n]+\*(?!\*))"
)


def render_inline(value: str) -> str:
    output: list[str] = []
    position = 0
    for match in INLINE_TOKEN.finditer(value):
        output.append(html.escape(value[position : match.start()]))
        token = match.group(0)
        if token.startswith("`"):
            output.append(
                f'<code style="font-family:{MONO};font-size:0.92em;'
                f'background:{SURFACE};border:1px solid {BORDER};border-radius:3px;'
                f'padding:1px 4px;">{html.escape(token[1:-1])}</code>'
            )
        elif token.startswith("["):
            label, url = token[1:].split("](", 1)
            target = safe_url(url[:-1])
            rendered_label = render_inline(label)
            if target is None:
                output.append(rendered_label)
            else:
                output.append(
                    f'<a href="{target}" style="color:{TEXT};text-decoration:underline;'
                    f'text-decoration-color:{MUTED};">{rendered_label}</a>'
                )
        elif token.startswith("**"):
            output.append(
                f'<strong style="font-weight:600;">{render_inline(token[2:-2])}</strong>'
            )
        else:
            output.append(f'<em style="font-style:italic;">{render_inline(token[1:-1])}</em>')
        position = match.end()
    output.append(html.escape(value[position:]))
    return "".join(output)


def split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def render_table(header: list[str], rows: list[list[str]]) -> str:
    cell_count = len(header)
    head = "".join(
        f'<th style="padding:8px 10px;border:1px solid {BORDER};background:{SURFACE};'
        f'text-align:left;font-family:{FONT};font-size:13px;line-height:1.4;'
        f'font-weight:600;color:{TEXT};">{render_inline(cell)}</th>'
        for cell in header
    )
    body_rows: list[str] = []
    for row in rows:
        padded = (row + [""] * cell_count)[:cell_count]
        cells = "".join(
            f'<td style="padding:8px 10px;border:1px solid {BORDER};text-align:left;'
            f'vertical-align:top;font-family:{FONT};font-size:13px;line-height:1.45;'
            f'color:{TEXT};">{render_inline(cell)}</td>'
            for cell in padded
        )
        body_rows.append(f'<tr style="margin:0;padding:0;">{cells}</tr>')
    return (
        '<table cellspacing="0" cellpadding="0" '
        f'style="width:100%;border-collapse:collapse;margin:16px 0;">'
        f'<thead style="margin:0;padding:0;"><tr style="margin:0;padding:0;">{head}</tr></thead>'
        f'<tbody style="margin:0;padding:0;">{"".join(body_rows)}</tbody></table>'
    )


def render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            content = "<br>".join(render_inline(line.strip()) for line in paragraph)
            blocks.append(
                f'<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;'
                f'line-height:1.6;color:{TEXT};">{content}</p>'
            )
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        if line.lstrip().startswith("```"):
            flush_paragraph()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith("```"):
                code.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(render_code("\n".join(code)))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            size = {1: 26, 2: 22, 3: 18, 4: 16, 5: 15, 6: 14}[level]
            margin = "0 0 18px" if level == 1 else "24px 0 10px"
            blocks.append(
                f'<h{level} style="margin:{margin};font-family:{FONT};font-size:{size}px;'
                f'line-height:1.25;font-weight:600;color:{TEXT};">'
                f'{render_inline(heading.group(2))}</h{level}>'
            )
            index += 1
            continue

        if index + 1 < len(lines) and "|" in line and is_table_separator(lines[index + 1]):
            flush_paragraph()
            header = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                rows.append(split_table_row(lines[index]))
                index += 1
            blocks.append(render_table(header, rows))
            continue

        list_match = re.match(r"^\s*([-+*]|\d+[.)])\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            ordered = list_match.group(1)[0].isdigit()
            items: list[str] = []
            while index < len(lines):
                item = re.match(r"^\s*([-+*]|\d+[.)])\s+(.+)$", lines[index])
                if not item or item.group(1)[0].isdigit() != ordered:
                    break
                items.append(item.group(2))
                index += 1
            tag = "ol" if ordered else "ul"
            rendered = "".join(
                f'<li style="margin:0 0 6px;padding:0;font-family:{FONT};font-size:15px;'
                f'line-height:1.55;color:{TEXT};">{render_inline(item)}</li>'
                for item in items
            )
            blocks.append(
                f'<{tag} style="margin:0 0 16px;padding-left:24px;color:{TEXT};">'
                f'{rendered}</{tag}>'
            )
            continue

        if re.fullmatch(r"\s*([-*_])(?:\s*\1){2,}\s*", line):
            flush_paragraph()
            blocks.append(f'<hr style="border:0;border-top:1px solid {BORDER};margin:22px 0;">')
            index += 1
            continue

        if line.startswith(">"):
            flush_paragraph()
            quote: list[str] = []
            while index < len(lines) and lines[index].startswith(">"):
                quote.append(lines[index][1:].lstrip())
                index += 1
            blocks.append(
                f'<blockquote style="margin:0 0 16px;padding:2px 0 2px 14px;'
                f'border-left:3px solid {BORDER};font-family:{FONT};font-size:15px;'
                f'line-height:1.55;color:{MUTED};">'
                f'{"<br>".join(render_inline(item) for item in quote)}</blockquote>'
            )
            continue

        if line.startswith("    ") or line.startswith("\t"):
            flush_paragraph()
            code = []
            while index < len(lines) and (
                lines[index].startswith("    ") or lines[index].startswith("\t")
            ):
                code.append(
                    lines[index][4:] if lines[index].startswith("    ") else lines[index][1:]
                )
                index += 1
            blocks.append(render_code("\n".join(code)))
            continue

        paragraph.append(line)
        index += 1

    flush_paragraph()
    return "".join(blocks)


def render_code(value: str) -> str:
    return (
        f'<pre style="margin:0 0 16px;padding:12px 14px;overflow-wrap:anywhere;'
        f'white-space:pre-wrap;background:{SURFACE};border:1px solid {BORDER};'
        f'border-radius:4px;font-family:{MONO};font-size:13px;line-height:1.5;'
        f'color:{TEXT};">{html.escape(value)}</pre>'
    )


FOOTER_MARKER = "\n\n— To continue this session, SSH into the Mac Studio and run:\n"


def render_document(markdown: str) -> str:
    if FOOTER_MARKER in markdown:
        main, command = markdown.rsplit(FOOTER_MARKER, 1)
        command = command.strip()
    else:
        main, command = markdown, ""

    footer = ""
    if command:
        footer = (
            f'<div style="margin:26px 0 0;padding:18px 0 0;border-top:1px solid {BORDER};">'
            f'<p style="margin:0 0 8px;font-family:{FONT};font-size:13px;line-height:1.5;'
            f'color:{MUTED};">— To continue this session, SSH into the Mac Studio and run:</p>'
            f'<pre style="margin:0;padding:10px 12px;white-space:pre-wrap;overflow-wrap:anywhere;'
            f'background:{SURFACE};border:1px solid {BORDER};border-radius:4px;'
            f'font-family:{MONO};font-size:12px;line-height:1.5;color:{TEXT};">'
            f'{html.escape(command)}</pre></div>'
        )

    content = render_markdown(main)
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#ffffff;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="width:100%;margin:0;padding:0;background:#ffffff;border-collapse:collapse;">'
        '<tr style="margin:0;padding:0;"><td align="center" style="margin:0;padding:24px 16px;">'
        f'<table role="presentation" width="680" cellspacing="0" cellpadding="0" '
        f'style="width:100%;max-width:680px;margin:0;border-collapse:collapse;">'
        f'<tr style="margin:0;padding:0;"><td style="margin:0;padding:0;font-family:{FONT};'
        f'font-size:15px;line-height:1.6;color:{TEXT};">{content}{footer}</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--from-address", required=True)
    parser.add_argument("--to-address", required=True)
    parser.add_argument("--subject", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    body = sys.stdin.read()
    message = EmailMessage(policy=SMTP)
    message["From"] = f"Borg {args.agent} <{args.from_address}>"
    message["To"] = args.to_address
    message["Subject"] = args.subject
    message["Date"] = formatdate(localtime=True)
    message.set_content(body, subtype="plain", charset="utf-8", cte="quoted-printable")
    message.add_alternative(
        render_document(body), subtype="html", charset="utf-8", cte="quoted-printable"
    )
    sys.stdout.buffer.write(message.as_bytes(policy=SMTP))


if __name__ == "__main__":
    main()
