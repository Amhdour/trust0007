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


def _normalize_requested_path(requested_path: str) -> str:
    candidate = requested_path.strip()
    if not candidate:
        return "/"
    return candidate if candidate.startswith("/") else f"/{candidate.lstrip('/')}"


def _activity_entry_summary(entry: dict[str, str]) -> dict[str, str]:
    return {
        "timestamp": str(entry.get("timestamp", "")),
        "summary": str(entry.get("summary", "")),
        "source_label": str(entry.get("source_label", "")),
        "event_type": str(entry.get("event_type", "")),
        "status": str(entry.get("status", "")),
        "severity": str(entry.get("severity", "")),
    }


def _matches_requested_path(entry: dict[str, str], requested_path: str) -> bool:
    if not requested_path or requested_path == "/":
        return False
    summary = str(entry.get("summary", ""))
    if requested_path in summary:
        return True
    path_only = requested_path.split("?", 1)[0]
    return bool(path_only and path_only != "/" and path_only in summary)


def _workspace_activity_row(
    entry: dict[str, str],
    *,
    scope: str,
    scope_label: str,
    correlation_detail: str,
    path_match: bool,
    trace_match: bool,
    session_match: bool,
) -> dict[str, str | bool]:
    request_id = str(entry.get("request_id", ""))
    return {
        "timestamp": str(entry.get("timestamp", "")),
        "source": str(entry.get("source", "")),
        "source_label": str(entry.get("source_label", "")),
        "event_type": str(entry.get("event_type", "")),
        "summary": str(entry.get("summary", "")),
        "severity": str(entry.get("severity", "")),
        "status": str(entry.get("status", "")),
        "trace_id": str(entry.get("trace_id", "")),
        "request_id": request_id,
        "session_id": request_id,
        "tenant_id": str(entry.get("tenant_id", "")),
        "scope": scope,
        "scope_label": scope_label,
        "correlation_detail": correlation_detail,
        "path_match": path_match,
        "trace_match": trace_match,
        "session_match": session_match,
    }


def build_onyx_workspace_activity(
    root: Path,
    *,
    requested_path: str = "",
    trace_id: str = "",
    session_id: str = "",
    limit: int = 6,
    activity_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_path = _normalize_requested_path(requested_path)
    snapshot_limit = max(limit * 4, 24)
    snapshot = activity_snapshot or build_activity_snapshot(root, limit=snapshot_limit)
    entries = list(snapshot.get("entries", []))

    current_surface: list[dict[str, str | bool]] = []
    correlated: list[dict[str, str | bool]] = []
    other_runtime: list[dict[str, str | bool]] = []

    for entry in entries:
        source = str(entry.get("source", ""))
        event_type = str(entry.get("event_type", ""))
        if source == "onyx" and event_type == "Onyx status":
            continue

        path_match = source == "onyx" and _matches_requested_path(entry, normalized_path)
        trace_match = bool(trace_id and str(entry.get("trace_id", "")) == trace_id)
        session_match = bool(session_id and str(entry.get("request_id", "")) == session_id)

        if path_match:
            current_surface.append(
                _workspace_activity_row(
                    entry,
                    scope="current_surface",
                    scope_label="This workspace path",
                    correlation_detail="Matched the governed Onyx path directly from runtime activity.",
                    path_match=path_match,
                    trace_match=trace_match,
                    session_match=session_match,
                )
            )
            continue

        if trace_match or session_match:
            matched_bits = []
            if trace_match:
                matched_bits.append("trace")
            if session_match:
                matched_bits.append("session")
            correlated.append(
                _workspace_activity_row(
                    entry,
                    scope="correlated",
                    scope_label="Correlated trace/session",
                    correlation_detail=(
                        f"Matched the governed {' and '.join(matched_bits)} in observability. "
                        "This correlation comes from trace/session evidence rather than raw Onyx container logs."
                    ),
                    path_match=path_match,
                    trace_match=trace_match,
                    session_match=session_match,
                )
            )
            continue

        if source == "onyx":
            other_runtime.append(
                _workspace_activity_row(
                    entry,
                    scope="other_runtime",
                    scope_label="Other Onyx runtime",
                    correlation_detail="Recent Onyx runtime activity is visible, but it does not match the current governed path.",
                    path_match=path_match,
                    trace_match=trace_match,
                    session_match=session_match,
                )
            )

    current_surface = current_surface[:limit]
    correlated = correlated[:limit]
    other_runtime = other_runtime[:limit]

    if current_surface:
        summary_status = "healthy"
        summary_label = "Direct runtime activity visible"
        summary_detail = (
            f"Showing {len(current_surface)} recent Onyx runtime event(s) that matched "
            f"{normalized_path} inside the dashboard-owned workspace."
        )
    elif correlated:
        summary_status = "warning"
        summary_label = "Correlated activity only"
        summary_detail = (
            "No direct Onyx path match is visible yet, but observability data is already tied to the same "
            "governed trace or session."
        )
    elif other_runtime:
        summary_status = "warning"
        summary_label = "Nearby runtime activity only"
        summary_detail = (
            "Onyx is active, but none of the recent runtime events matched the current governed path or correlated identifiers."
        )
    else:
        summary_status = "critical"
        summary_label = "No recent Onyx activity visible"
        summary_detail = (
            "No recent Onyx runtime activity or correlated observability events were found for this workspace yet."
        )

    return {
        "generated_at": _now_iso(),
        "poll_interval_ms": int(snapshot.get("poll_interval_ms", 5000) or 5000),
        "requested_path": normalized_path,
        "trace_id": trace_id,
        "session_id": session_id,
        "source_href": "/api/control-plane/onyx-activity?" + urllib.parse.urlencode(
            {
                "path": normalized_path,
                "trace_id": trace_id,
                "session_id": session_id,
                "limit": limit,
            }
        ),
        "sources": {
            "onyx": str(snapshot.get("sources", {}).get("onyx", "")),
            "langfuse": str(snapshot.get("sources", {}).get("langfuse", "")),
        },
        "summary": {
            "status": summary_status,
            "label": summary_label,
            "detail": summary_detail,
        },
        "counts": {
            "current_surface": len(current_surface),
            "correlated": len(correlated),
            "other_runtime": len(other_runtime),
        },
        "groups": [
            {
                "id": "current-surface",
                "title": "This workspace path",
                "description": "Direct runtime events that matched the current Onyx path in the embedded workspace.",
                "entries": current_surface,
                "empty_state": "No direct runtime hits for this path yet.",
            },
            {
                "id": "correlated",
                "title": "Correlated trace or session",
                "description": "Observability events linked to the same governed trace or session when the runtime logs themselves do not expose those identifiers.",
                "entries": correlated,
                "empty_state": "No correlated trace/session activity was found yet.",
            },
            {
                "id": "other-runtime",
                "title": "Other recent Onyx runtime",
                "description": "Nearby Onyx activity seen in the same runtime, kept visible so you can tell whether the stack is active even when this workspace has not produced a direct match yet.",
                "entries": other_runtime,
                "empty_state": "No unrelated recent Onyx runtime activity was captured.",
            },
        ],
        "limitations": [
            "Direct Onyx runtime rows are matched by path because current container logs do not expose governed trace or session identifiers.",
            "Trace and session correlation comes from observability signals such as Langfuse when those identifiers are available.",
        ],
    }


def build_onyx_runtime_proof(
    root: Path,
    *,
    requested_path: str = "",
    trace_id: str = "",
    session_id: str = "",
    activity_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = activity_snapshot or build_activity_snapshot(root)
    normalized_path = _normalize_requested_path(requested_path)
    onyx_entries = [
        entry
        for entry in snapshot.get("entries", [])
        if entry.get("source") == "onyx" and entry.get("event_type") != "Onyx status"
    ]
    matched_entries = [entry for entry in onyx_entries if _matches_requested_path(entry, normalized_path)]
    latest_activity = matched_entries[0] if matched_entries else (onyx_entries[0] if onyx_entries else {})

    if matched_entries:
        continuity_status = "path_activity_observed"
        continuity_label = "Path activity seen"
        continuity_detail = (
            "Recent Onyx activity matched the governed target path. Trace and session identifiers remain linked "
            "through control-plane artifacts rather than current Onyx container logs."
        )
    elif onyx_entries:
        continuity_status = "runtime_activity_observed"
        continuity_label = "Runtime activity seen"
        continuity_detail = (
            "Recent Onyx activity is visible, but the current runtime logs do not expose the same trace or session "
            "identifiers, so continuity remains anchored in the control-plane trace."
        )
    else:
        continuity_status = "no_runtime_activity"
        continuity_label = "No recent activity"
        continuity_detail = (
            "No recent Onyx container activity was found. The control plane still has the governed handoff trace, "
            "but there is no fresh runtime activity to compare against it yet."
        )

    return {
        "generated_at": _now_iso(),
        "runtime_target": "onyx",
        "requested_path": normalized_path,
        "trace_id": trace_id,
        "session_id": session_id,
        "activity_source_status": str(snapshot.get("sources", {}).get("onyx", "")),
        "activity_observed": bool(onyx_entries),
        "activity_count": len(onyx_entries),
        "requested_path_activity_observed": bool(matched_entries),
        "requested_path_activity_count": len(matched_entries),
        "latest_activity": _activity_entry_summary(latest_activity) if latest_activity else {},
        "matched_activity": _activity_entry_summary(matched_entries[0]) if matched_entries else {},
        "continuity": {
            "status": continuity_status,
            "label": continuity_label,
            "detail": continuity_detail,
            "trace_visible_in_runtime": False,
            "session_visible_in_runtime": False,
        },
    }
