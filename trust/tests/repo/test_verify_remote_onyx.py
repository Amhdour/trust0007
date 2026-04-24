from __future__ import annotations

import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _write_env_file(content: str) -> str:
    fd, path = tempfile.mkstemp(prefix="verify-remote-onyx-", suffix=".env")
    os.close(fd)
    Path(path).write_text(content, encoding="utf-8")
    return path


def test_verify_remote_onyx_skips_when_local_mode_enabled() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    try:
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = int(server.server_address[1])

        env_file = _write_env_file(
            "\n".join(
                [
                    "CONTROL_PLANE_USE_LOCAL_ONYX=true",
                    f"CONTROL_PLANE_ONYX_BASE_URL=http://127.0.0.1:{port}",
                    f"CONTROL_PLANE_ONYX_API_BASE_URL=http://127.0.0.1:{port}/api",
                ]
            )
            + "\n"
        )

        result = subprocess.run(
            ["bash", "scripts/verify-remote-onyx.sh", env_file],
            cwd=Path(__file__).resolve().parents[2],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    finally:
        server.shutdown()
        server.server_close()


def test_verify_remote_onyx_fails_for_missing_urls() -> None:
    env_file = _write_env_file("CONTROL_PLANE_USE_LOCAL_ONYX=false\n")
    result = subprocess.run(
        ["bash", "scripts/verify-remote-onyx.sh", env_file],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "CONTROL_PLANE_ONYX_BASE_URL" in result.stderr


def test_verify_remote_onyx_rejects_localhost_in_remote_mode() -> None:
    env_file = _write_env_file(
        "\n".join(
            [
                "CONTROL_PLANE_USE_LOCAL_ONYX=false",
                "CONTROL_PLANE_ONYX_BASE_URL=http://localhost:3000",
                "CONTROL_PLANE_ONYX_API_BASE_URL=http://localhost:3000/api",
            ]
        )
        + "\n"
    )
    result = subprocess.run(
        ["bash", "scripts/verify-remote-onyx.sh", env_file],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "cannot point to localhost" in result.stderr


def test_verify_remote_onyx_rejects_workspace_path_urls() -> None:
    env_file = _write_env_file(
        "\n".join(
            [
                "CONTROL_PLANE_USE_LOCAL_ONYX=false",
                "CONTROL_PLANE_ONYX_BASE_URL=/workspaces/trust0007/upstream/onyx",
                "CONTROL_PLANE_ONYX_API_BASE_URL=/workspaces/trust0007/upstream/onyx/api",
            ]
        )
        + "\n"
    )
    result = subprocess.run(
        ["bash", "scripts/verify-remote-onyx.sh", env_file],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "filesystem path" in result.stderr
