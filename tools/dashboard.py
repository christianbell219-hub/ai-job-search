#!/usr/bin/env python3
"""Local job-search dashboard (localhost only).

Reads tracker + seen_jobs + application archives. Drafting still happens in Claude.

    python3 tools/dashboard.py
    python3 tools/dashboard.py --port 8765 --root /path/to/repo

Opens http://127.0.0.1:8765 — never binds a public interface.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from job_pipeline import (  # noqa: E402
    build_state,
    resolve_allowed_file,
    set_portal_enabled,
    update_tracker_status,
)

STATIC_DIR = ROOT / "dashboard"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def make_handler(repo_root: Path):
    class DashboardHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send(self, code: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if extra:
                for key, value in extra.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
            return data

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path in {"/", "/index.html"}:
                index = STATIC_DIR / "index.html"
                self._send(200, index.read_bytes(), "text/html; charset=utf-8")
                return
            if path.startswith("/static/"):
                rel = path[len("/static/") :]
                target = (STATIC_DIR / rel).resolve()
                if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                    self._json(404, {"error": "not found"})
                    return
                mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                self._send(200, target.read_bytes(), mime)
                return
            if path == "/api/state":
                self._json(200, build_state(repo_root))
                return
            if path == "/file":
                rel = (parse_qs(parsed.query).get("path") or [""])[0]
                try:
                    target = resolve_allowed_file(repo_root, rel)
                except PermissionError:
                    self._json(403, {"error": "path not allowed"})
                    return
                except FileNotFoundError:
                    self._json(404, {"error": "not found"})
                    return
                mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                extra = {"Content-Disposition": f'inline; filename="{target.name}"'}
                self._send(200, target.read_bytes(), mime, extra)
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            if parsed.path == "/api/status":
                company = str(payload.get("company") or "").strip()
                role = str(payload.get("role") or "").strip()
                status = str(payload.get("status") or "").strip()
                if not company or not role or not status:
                    self._json(400, {"error": "company, role, and status are required"})
                    return
                try:
                    row = update_tracker_status(repo_root, company, role, status)
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                    return
                except FileNotFoundError as exc:
                    self._json(404, {"error": str(exc)})
                    return
                self._json(200, {"ok": True, "row": row})
                return
            if parsed.path == "/api/portals":
                name = str(payload.get("name") or "").strip()
                if "enabled" not in payload:
                    self._json(400, {"error": "enabled is required"})
                    return
                enabled = bool(payload["enabled"])
                try:
                    portal = set_portal_enabled(repo_root, name, enabled)
                except FileNotFoundError as exc:
                    self._json(404, {"error": str(exc)})
                    return
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                    return
                self._json(200, {"ok": True, "portal": portal})
                return
            self._json(404, {"error": "not found"})

    return DashboardHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local job-search dashboard (127.0.0.1 only)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind address (default 127.0.0.1)")
    args = parser.parse_args(argv)
    host = args.host
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("dashboard binds localhost only; refusing host %s" % host, file=sys.stderr)
        return 2
    root = args.root.resolve()
    httpd = ThreadingHTTPServer((host, args.port), make_handler(root))
    url = f"http://{host}:{args.port}"
    print(f"Job search dashboard → {url}")
    print("Drafting still happens in Claude (/apply, /scrape, /interview). Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
