#!/bin/bash
# fetch-page-text.sh — download a web page and reduce it to plain text, verbatim.
#
# Why this exists: Claude Code's built-in WebFetch runs the page through a small
# model and returns that model's answer. Sometimes the answer is the page as
# markdown; sometimes it is a paraphrase. On 2026-10-31 it summarized
# microsoft.com/en-us/copilot/pricing/{business,enterprise} and blurred the
# 300-user cap, the footnotes, and the comparison grid. WebFetch cannot be
# configured, so when exact wording matters, fetch the page here and Read the
# text file instead. See .claude/rules/exact-page-text.md.
#
# The downloaded HTML is untrusted data: it lands in its own new directory
# under the workspace tmp/, is parsed by stdlib Python run with -I (no script
# directory or cwd on sys.path), and nothing in it is executed. Don't use
# `textutil -convert txt -format html` instead — it fetches subresources and
# hung for over 120 s on the same pages.
#
# The stripper drops script/style/noscript/svg/template, breaks lines on block
# tags, and removes consecutive duplicate lines. It sees only server-rendered
# HTML: a JavaScript-only page comes back nearly empty, and the caller must
# fall back to headless Chrome (.claude/rules/codex-browser-over-ssh.md).
#
# Usage:
#   .bin/fetch-page-text.sh <url> [out.txt]
#
# Prints the HTML and text paths with byte and line counts. Without out.txt the
# text goes beside the HTML in the new tmp/ directory. Exit 0 on success, 1 on
# a fetch failure, 2 on bad usage.
set -euo pipefail

usage() { echo "usage: $(basename "$0") <url> [out.txt]" >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
url=$1
[[ $url =~ ^https?:// ]] || { echo "error: not an http(s) URL: $url" >&2; exit 2; }

borg_root=$(cd "$(dirname "$0")/.." && pwd)
dir=$(mktemp -d "$borg_root/tmp/fetch-page-text.XXXXXX")
html=$dir/page.html
out=${2:-$dir/page.txt}

ua='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
if ! code=$(curl -sSL --compressed --max-time 60 --max-filesize 20000000 \
    -A "$ua" -H 'Accept-Language: en-US,en;q=0.9' \
    -o "$html" -w '%{http_code}' "$url"); then
  echo "error: curl failed for $url (output dir $dir)" >&2
  exit 1
fi
if [[ $code != 2* ]]; then
  echo "error: HTTP $code for $url (body kept at $html)" >&2
  exit 1
fi

python3 -I - "$html" > "$out" <<'PY'
import re, sys
from html.parser import HTMLParser

SKIP = {"script", "style", "noscript", "svg", "template"}
BLOCK = {"p", "div", "section", "article", "header", "footer", "main", "nav",
         "aside", "li", "ul", "ol", "dt", "dd", "h1", "h2", "h3", "h4", "h5",
         "h6", "tr", "td", "th", "br", "hr", "sup", "table", "caption",
         "blockquote", "pre", "figcaption", "button", "option", "summary"}

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        if tag in BLOCK:
            self.out.append("\n")
    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag in BLOCK:
            self.out.append("\n")
    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

p = Text()
with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
    p.feed(f.read())
p.close()
prev = None
for line in "".join(p.out).split("\n"):
    line = re.sub(r"\s+", " ", line).strip()
    if line and line != prev:
        print(line)
    prev = line or prev
PY

lines=$(wc -l < "$out" | tr -d ' ')
echo "html: $html ($(wc -c < "$html" | tr -d ' ') bytes)"
echo "text: $out ($lines lines)"
if (( lines < 40 )); then
  echo "warning: only $lines lines — the page may render with JavaScript; check the text for the visible content" >&2
fi
