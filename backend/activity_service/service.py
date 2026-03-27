from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
import http.client
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import re
from typing import Any


DOCKER_SOCKET_PATH = "/var/run/docker.sock"
DOCKER_API_PREFIX = "/v1.41"
LANGFUSE_BASE_URL = "http://langfuse:3000"
DEFAULT_ACTIVITY_LIMIT = 12

ONYX_CONTAINERS = (
    {
        "name": "onyx-nginx-1",
        "source": "onyx",
        "source_label": "Onyx Web",
        "event_type": "Onyx web request",
    },
    {
        "name": "onyx-api_server-1",
        "source": "onyx",
        "source_label": "Onyx API",
        "event_type": "Onyx API request",
    },
    {
        "name": "onyx-web_server-1",
        "source": "onyx",
        "source_label": "Onyx App",
        "event_type": "Onyx app event",
    },
)

HTTP_REQUEST_PATTERN = re.compile(r'"(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (?P<path>[^ ]+) HTTP/[^"]+" (?P<status>\d{3})')


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_socket_path: str, host: str = "localhost", timeout: float = 5.0) -> None:
        super().__init__(host=host, timeout=timeout)
        self.unix_socket_path = unix_socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.unix_socket_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_from_severity(severity: str) -> str:
    normalized = severity.strip().lower()
    return {
        "critical": "critical",
        "error": "critical",
        "warning": "warning",
        "warn": "warning",
        "healthy": "healthy",
        "info": "neutral",
        "neutral": "neutral",
        "debug": "neutral",
    }.get(normalized, "neutral")


def _parse_iso_timestamp(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        base = candidate[:-1]
        suffix = "+00:00"
    else:
        base = candidate
        suffix = ""

    if "." in base:
        head, fractional = base.split(".", 1)
        fractional_digits = "".join(ch for ch in fractional if ch.isdigit())
        base = f"{head}.{(fractional_digits + '000000')[:6]}"

    parsed = datetime.fromisoformat(f"{base}{suffix}")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _format_entry(
    *,
    timestamp: datetime,
    source: str,
    source_label: str,
    event_type: str,
    summary: str,
    severity: str,
    status: str | None = None,
    request_id: str = "",
    trace_id: str = "",
    tenant_id: str = "",
) -> dict[str, str]:
    return {
        "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
        "source": source,
        "source_label": source_label,
        "event_type": event_type,
        "summary": summary,
        "severity": severity,
        "status": status or _status_from_severity(severity),
        "request_id": request_id,
        "trace_id": trace_id,
        "tenant_id": tenant_id,
    }


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _langfuse_auth_header(root: Path) -> str | None:
    env = _parse_env_file(root / "compose/.env")
    public_key = env.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY", "")
    secret_key = env.get("LANGFUSE_INIT_PROJECT_SECRET_KEY", "")
    if not public_key or not secret_key:
        return None
    token = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _http_json(url: str, auth_header: str | None = None, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(url)
    if auth_header:
        request.add_header("Authorization", auth_header)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _docker_api_get(path: str, timeout: float = 5.0) -> bytes:
    connection = UnixSocketHTTPConnection(DOCKER_SOCKET_PATH, timeout=timeout)
    try:
        connection.request("GET", f"{DOCKER_API_PREFIX}{path}")
        response = connection.getresponse()
        payload = response.read()
        if response.status >= 400:
            raise RuntimeError(f"Docker API returned {response.status} for {path}")
        return payload
    finally:
        connection.close()


def _docker_api_json(path: str, timeout: float = 5.0) -> Any:
    return json.loads(_docker_api_get(path, timeout=timeout).decode("utf-8"))


def _decode_docker_log_stream(payload: bytes) -> str:
    if not payload:
        return ""

    if len(payload) >= 8 and payload[0] in {1, 2} and payload[1:4] == b"\x00\x00\x00":
        chunks: list[str] = []
        index = 0
        while index + 8 <= len(payload):
            frame_size = int.from_bytes(payload[index + 4 : index + 8], "big")
            index += 8
            frame = payload[index : index + frame_size]
            chunks.append(frame.decode("utf-8", errors="replace"))
            index += frame_size
        return "".join(chunks)

    return payload.decode("utf-8", errors="replace")


def _docker_container_ids() -> dict[str, str]:
    containers = _docker_api_json("/containers/json?all=1", timeout=6.0)
    by_name: dict[str, str] = {}
    for container in containers:
        names = [name.lstrip("/") for name in container.get("Names", [])]
        for name in names:
            by_name[name] = str(container.get("Id", ""))
    return by_name


def _parse_docker_timestamped_line(line: str) -> tuple[datetime | None, str]:
    if not line.strip():
        return None, ""
    if " " not in line:
        return None, line.strip()
    raw_timestamp, message = line.split(" ", 1)
    try:
        return _parse_iso_timestamp(raw_timestamp), message.strip()
    except ValueError:
        return None, line.strip()


def _severity_from_status_code(status_code: int) -> str:
    if status_code >= 500:
        return "error"
    if status_code >= 400:
        return "warning"
    return "info"


def _parse_onyx_log_lines(*, source: str, source_label: str, event_type: str, raw_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in raw_text.splitlines():
        timestamp, message = _parse_docker_timestamped_line(line)
        if not timestamp or not message:
            continue

        request_match = HTTP_REQUEST_PATTERN.search(message)
        if request_match:
            method = request_match.group("method")
            path = request_match.group("path")
            status_code = int(request_match.group("status"))
            if path in {"/health", "/api/health"}:
                continue
            entries.append(
                _format_entry(
                    timestamp=timestamp,
                    source=source,
                    source_label=source_label,
                    event_type=event_type,
                    summary=f"{method} {path} -> {status_code}",
                    severity=_severity_from_status_code(status_code),
                )
            )
            continue

        if source_label == "Onyx App" and "Login page:" in message:
            entries.append(
                _format_entry(
                    timestamp=timestamp,
                    source=source,
                    source_label=source_label,
                    event_type=event_type,
                    summary="User session redirected into Onyx chat",
                    severity="info",
                )
            )

    return entries


def _load_onyx_activity(limit: int) -> tuple[list[dict[str, str]], str]:
    if not Path(DOCKER_SOCKET_PATH).exists():
        return [], "docker socket unavailable"

    try:
        container_ids = _docker_container_ids()
    except Exception as exc:  # noqa: BLE001
        return [], f"docker unavailable: {exc}"

    entries: list[dict[str, str]] = []
    for target in ONYX_CONTAINERS:
        container_id = container_ids.get(target["name"])
        if not container_id:
            continue
        try:
            query = urllib.parse.urlencode(
                {
                    "stdout": 1,
                    "stderr": 1,
                    "tail": max(limit * 4, 20),
                    "timestamps": 1,
                }
            )
            raw_logs = _docker_api_get(f"/containers/{container_id}/logs?{query}", timeout=8.0)
            decoded_logs = _decode_docker_log_stream(raw_logs)
            entries.extend(
                _parse_onyx_log_lines(
                    source=target["source"],
                    source_label=target["source_label"],
                    event_type=target["event_type"],
                    raw_text=decoded_logs,
                )
            )
        except Exception:  # noqa: BLE001
            continue

    if entries:
        entries.sort(key=lambda item: item["timestamp"], reverse=True)
        return entries[: limit * 2], "connected"
    return [], "no recent Onyx activity"


def _load_langfuse_activity(root: Path, limit: int) -> tuple[list[dict[str, str]], str]:
    auth_header = _langfuse_auth_header(root)
    if not auth_header:
        return [], "Langfuse API keys not configured"

    try:
        traces = _http_json(f"{LANGFUSE_BASE_URL}/api/public/traces?limit={limit}&orderBy=timestamp.desc", auth_header)
        sessions = _http_json(f"{LANGFUSE_BASE_URL}/api/public/sessions?limit={limit}", auth_header)
    except urllib.error.URLError as exc:
        return [], f"Langfuse unavailable: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return [], f"Langfuse error: {exc}"

    entries: list[dict[str, str]] = []

    for trace in traces.get("data", []):
        try:
            timestamp = _parse_iso_timestamp(str(trace.get("timestamp") or trace.get("createdAt") or _now_iso()))
        except ValueError:
            timestamp = datetime.now(timezone.utc)
        trace_name = str(trace.get("name") or "trace")
        trace_id = str(trace.get("id", ""))
        session_id = str(trace.get("sessionId") or "")
        entries.append(
            _format_entry(
                timestamp=timestamp,
                source="langfuse",
                source_label="Langfuse Trace",
                event_type="Langfuse trace",
                summary=f"Trace captured: {trace_name}",
                severity="info",
                trace_id=trace_id,
                request_id=session_id,
            )
        )

    for session in sessions.get("data", []):
        try:
            timestamp = _parse_iso_timestamp(str(session.get("createdAt") or _now_iso()))
        except ValueError:
            timestamp = datetime.now(timezone.utc)
        session_id = str(session.get("id", ""))
        entries.append(
            _format_entry(
                timestamp=timestamp,
                source="langfuse",
                source_label="Langfuse Session",
                event_type="Langfuse session",
                summary=f"Session recorded in Langfuse: {session_id[:8]}",
                severity="info",
                request_id=session_id,
            )
        )

    if entries:
        entries.sort(key=lambda item: item["timestamp"], reverse=True)
        return entries[: limit * 2], "connected"
    return [], "connected, no traces yet"


def build_activity_snapshot(root: Path, limit: int = DEFAULT_ACTIVITY_LIMIT) -> dict[str, Any]:
    onyx_entries, onyx_status = _load_onyx_activity(limit)
    langfuse_entries, langfuse_status = _load_langfuse_activity(root, limit)
    real_entries = onyx_entries + langfuse_entries

    combined_entries = list(real_entries)
    if not langfuse_entries:
        combined_entries.append(
            _format_entry(
                timestamp=datetime.now(timezone.utc),
                source="langfuse",
                source_label="Langfuse",
                event_type="Langfuse status",
                summary="Langfuse is connected but no trace activity has been captured yet.",
                severity="info" if langfuse_status.startswith("connected") else "warning",
            )
        )
    if not onyx_entries:
        combined_entries.append(
            _format_entry(
                timestamp=datetime.now(timezone.utc),
                source="onyx",
                source_label="Onyx",
                event_type="Onyx status",
                summary="No recent Onyx activity was found from the running containers.",
                severity="warning",
            )
        )

    combined_entries.sort(key=lambda item: item["timestamp"], reverse=True)
    combined_entries = combined_entries[:limit]

    counts = Counter(entry["source"] for entry in real_entries)
    alerts = sum(1 for entry in real_entries if entry["status"] in {"warning", "critical"})
    langfuse_traces = sum(1 for entry in real_entries if entry["event_type"] == "Langfuse trace")
    langfuse_sessions = sum(1 for entry in real_entries if entry["event_type"] == "Langfuse session")

    return {
        "generated_at": _now_iso(),
        "poll_interval_ms": 5000,
        "source_href": "/api/control-plane/live-log?limit=50",
        "entries": combined_entries,
        "counts": {
            "combined": len(real_entries),
            "onyx": counts.get("onyx", 0),
            "langfuse": counts.get("langfuse", 0),
            "alerts": alerts,
            "langfuse_traces": langfuse_traces,
            "langfuse_sessions": langfuse_sessions,
        },
        "sources": {
            "onyx": onyx_status,
            "langfuse": langfuse_status,
        },
    }
