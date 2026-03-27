from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from backend.posture_service.service import build_control_plane_dashboard, build_control_plane_live_log


REPO_ROOT = Path(os.environ.get("CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
STATIC_ROOT = REPO_ROOT / "frontend/main-dashboard"


class ControlPlaneRequestHandler(BaseHTTPRequestHandler):
    server_version = "control-plane/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/api/health", "/healthz"}:
            self._send_json({"status": "ok"})
            return

        if path in {"/api/control-plane", "/api/control-plane/overview"}:
            self._send_json(build_control_plane_dashboard(REPO_ROOT))
            return

        if path == "/api/control-plane/live-log":
            limit = self._parse_int_query(parse_qs(parsed.query).get("limit", ["12"])[0], default=12, minimum=1, maximum=50)
            self._send_json(build_control_plane_live_log(REPO_ROOT, limit=limit))
            return

        if path.startswith("/raw/"):
            self._serve_repo_file(path.removeprefix("/raw/"))
            return

        self._serve_static(path)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _parse_int_query(self, raw_value: str, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(raw_value)
        except ValueError:
            return default
        return max(minimum, min(maximum, parsed))

    def _serve_static(self, request_path: str) -> None:
        relative_path = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (STATIC_ROOT / relative_path).resolve()
        if not candidate.exists() or not candidate.is_file() or STATIC_ROOT not in candidate.parents and candidate != STATIC_ROOT / "index.html":
            candidate = STATIC_ROOT / "index.html"
        self._send_file(candidate)

    def _serve_repo_file(self, relative_path: str) -> None:
        candidate = (REPO_ROOT / unquote(relative_path)).resolve()
        if not candidate.exists() or not candidate.is_file() or REPO_ROOT not in candidate.parents:
            self.send_error(HTTPStatus.NOT_FOUND.value, "File not found")
            return
        self._send_file(candidate)

    def _send_file(self, path: Path) -> None:
        content = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", f"{mime_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run() -> None:
    host = os.environ.get("CONTROL_PLANE_HOST", "0.0.0.0")
    port = int(os.environ.get("CONTROL_PLANE_PORT", "3000"))
    server = ThreadingHTTPServer((host, port), ControlPlaneRequestHandler)
    print(f"Control plane listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
