#!/usr/bin/env python3
"""Minimal static server for ~/briefs — loopback only, no directory listing.

Exposed publicly via Tailscale Funnel; the unguessable filename is the access
control, so listing must never work and only .html files are served.
"""
import http.server
from pathlib import Path

BIND = ("127.0.0.1", 8377)
BRIEFS_DIR = str(Path.home() / "briefs")


class BriefHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BRIEFS_DIR, **kwargs)

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def do_GET(self):
        if not self.path.split("?")[0].endswith(".html"):
            self.send_error(404, "Not found")
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "private, max-age=300")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # tokens appear in request paths; keep them out of logs


if __name__ == "__main__":
    Path(BRIEFS_DIR).mkdir(mode=0o700, exist_ok=True)
    http.server.ThreadingHTTPServer(BIND, BriefHandler).serve_forever()
