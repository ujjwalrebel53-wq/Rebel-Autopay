#!/usr/bin/env python3
"""
Tower Intel Hub — local web server.

Serves the dashboard and optionally proxies the tower collector API
to avoid CORS issues during development.

Usage:
  python3 web/server.py
  python3 web/server.py --port 8080 --collector http://localhost:8787
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent
COLLECTOR_URL = "http://127.0.0.1:8787"


class HubHandler(SimpleHTTPRequestHandler):
    collector_url = COLLECTOR_URL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/towers"):
            self._proxy_get("/towers")
            return
        if self.path.startswith("/api/health"):
            self._proxy_get("/health")
            return
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/report"):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            self._proxy_post("/report", body)
            return
        self.send_error(404)

    def _proxy_get(self, endpoint: str) -> None:
        url = f"{self.collector_url.rstrip('/')}{endpoint}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.URLError as exc:
            self._json_error(502, f"Collector unreachable: {exc}")

    def _proxy_post(self, endpoint: str, body: bytes) -> None:
        url = f"{self.collector_url.rstrip('/')}{endpoint}"
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            self.send_response(resp.status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.URLError as exc:
            self._json_error(502, f"Collector unreachable: {exc}")

    def _json_error(self, code: int, message: str) -> None:
        payload = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        print(f"[hub] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tower Intel Hub web server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--collector", default=COLLECTOR_URL, help="Tower collector base URL")
    args = parser.parse_args()

    HubHandler.collector_url = args.collector
    server = ThreadingHTTPServer((args.host, args.port), HubHandler)
    print(f"Tower Intel Hub: http://{args.host}:{args.port}")
    print(f"Collector proxy: /api/towers -> {args.collector}/towers")
    print("Camera requires HTTPS or localhost — use this local server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
