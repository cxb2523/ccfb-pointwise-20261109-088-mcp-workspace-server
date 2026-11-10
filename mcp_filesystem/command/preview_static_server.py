"""Lightweight static file server with SPA-style fallback to a chosen entry file.

This avoids the clean-URL behavior of the Node `serve` CLI so that explicit
`.html` entry files remain accessible without redirection.
"""

import argparse
import signal
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse


class PreviewRequestHandler(SimpleHTTPRequestHandler):
    """Serve static files with fallback to a configured entry file."""

    def __init__(self, *args, directory: Optional[str] = None, entry: str = "index.html", **kwargs):
        self.entry = entry
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        """Quiet logging to avoid noisy stdout."""
        return

    def send_head(self):
        """Serve requested path or fall back to the entry file for SPA routes."""
        parsed = urlparse(self.path)
        rel_path = unquote(parsed.path.lstrip("/"))

        base_dir = Path(self.directory or ".")
        requested_path = (base_dir / rel_path).resolve()

        # If the requested path does not exist, fall back to the entry file
        if not requested_path.exists() or not str(requested_path).startswith(str(base_dir)):
            fallback = (base_dir / self.entry).resolve()
            if fallback.exists() and str(fallback).startswith(str(base_dir)):
                # Rewrite to entry for SPA-style routing
                self.path = "/" + self.entry
            else:
                self.send_error(404, "File not found")
                return None

        return super().send_head()


def run_server(host: str, port: int, root: Path, entry: str) -> None:
    handler = partial(PreviewRequestHandler, directory=str(root), entry=entry)
    httpd = ThreadingHTTPServer((host, port), handler)

    def _shutdown(*_):
        httpd.shutdown()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="Preview static server with entry fallback")
    parser.add_argument("--port", type=int, required=True, help="Port to bind")
    parser.add_argument("--root", type=str, required=True, help="Directory to serve")
    parser.add_argument("--entry", type=str, default="index.html", help="Entry file for SPA fallback")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        sys.stderr.write(f"Root directory does not exist: {root}\n")
        sys.exit(1)

    run_server(args.host, args.port, root, args.entry)


if __name__ == "__main__":
    main()
