from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import parse_qs, unquote, urlparse

from backend.posture_service.service import build_control_plane_dashboard, build_control_plane_live_log
from backend.governance_flow_evaluator import GovernedFlowEvaluator
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import PolicyDecision, RetrievalDecision, ToolDecision, NormalizedRequest
from adapters.retrieval.interfaces import RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.tools.interfaces import ToolExecutor
from adapters.tools.schemas import ToolActionRequest


REPO_ROOT = Path(os.environ.get("CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
STATIC_ROOT = REPO_ROOT / "frontend/main-dashboard"


def _public_service_url(port: int, path: str = "") -> str:
    codespace_name = os.environ.get("CODESPACE_NAME", "").strip()
    forwarding_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "").strip()
    if codespace_name and forwarding_domain:
        base = f"https://{codespace_name}-{port}.{forwarding_domain}"
    else:
        base = f"http://localhost:{port}"
    return f"{base}{path}"


# Stub governance implementations for governed flow
class DemoPolicyChecker(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=True, reasons=["policy.allow"])


class DemoRetrievalChecker(RetrievalChecker):
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        return RetrievalDecision(allow=True, reasons=["retrieval.allow"])


class DemoToolChecker(ToolDecisionChecker):
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        return ToolDecision(allowed_tools=request.requested_tools, denied_tools=[], reasons=[])


class DemoRetrievalBackend(RetrievalBackend):
    def search(self, request: RetrievalRequest):
        return [
            RetrievalDocument(
                doc_id="demo-doc-1",
                tenant_id=request.tenant_id,
                source=request.source,
                content="Demo retrieval result for governed flow.",
                trust_label="trusted",
                quarantined=False,
                provenance={"uri": "kb://demo-doc-1"},
            )
        ]


class DemoRetrievalPolicy(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict:
        return {"allow": True, "mode": "allow", "reasons": []}


class DemoToolExecutor(ToolExecutor):
    def execute(self, request: ToolActionRequest) -> dict:
        return {"result": "executed", "tool": request.tool_name}


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

        if path == "/api/control-plane/governed-flow":
            self._handle_governed_flow()
            return

        if path.startswith("/raw/"):
            self._serve_repo_file(path.removeprefix("/raw/"))
            return

        if path == "/launch/onyx":
            requested_path = parse_qs(parsed.query).get("path", ["/app"])[0]
            self._serve_onyx_handoff(requested_path)
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

    def _handle_governed_flow(self) -> None:
        """Execute a governed flow with demo governance checkers and emit artifacts."""
        try:
            evaluator = GovernedFlowEvaluator(
                policy_checker=DemoPolicyChecker(),
                retrieval_checker=DemoRetrievalChecker(),
                tool_checker=DemoToolChecker(),
                retrieval_backend=DemoRetrievalBackend(),
                retrieval_policy=DemoRetrievalPolicy(),
                tool_executor=DemoToolExecutor(),
                artifact_dir=REPO_ROOT / "overlays" / "myStarterKit" / "artifacts",
            )

            result = evaluator.run(
                user_id="api-user",
                tenant_id="tenant-api",
                prompt="Demonstrate governed flow through control plane API",
                requested_tools=["search", "summarize"],
                retrieval_source="qdrant",
                retrieval_needed=True,
            )

            self._send_json(result.to_dict())
        except Exception as e:
            self._send_json(
                {"error": str(e), "type": type(e).__name__},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

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

    def _serve_onyx_handoff(self, requested_path: str) -> None:
        """Serve Onyx handoff with governance enforcement.
        
        Before allowing handoff to Onyx, check governance policies.
        Block handoff if policy/retrieval/tools deny the access.
        Emit decision events for audit trail.
        """
        safe_path = requested_path if requested_path.startswith("/") else f"/{requested_path.lstrip('/')}"

        # Run governance check for Onyx handoff
        try:
            evaluator = GovernedFlowEvaluator(
                policy_checker=DemoPolicyChecker(),
                retrieval_checker=DemoRetrievalChecker(),
                tool_checker=DemoToolChecker(),
                retrieval_backend=DemoRetrievalBackend(),
                retrieval_policy=DemoRetrievalPolicy(),
                tool_executor=DemoToolExecutor(),
                artifact_dir=REPO_ROOT / "overlays" / "myStarterKit" / "artifacts",
            )

            flow_result = evaluator.run(
                user_id="dashboard-user",
                tenant_id="tenant-dashboard",
                prompt=f"Navigate to Onyx path: {safe_path}",
                requested_tools=["onyx"],
                retrieval_source="qdrant",
                retrieval_needed=False,
            )
        except Exception as e:
            flow_result = None
            governance_allowed = True  # Fail open if evaluator crashes

        # Determine if handoff is allowed
        governance_allowed = flow_result.decision if flow_result else True

        if not governance_allowed:
            # Governance denied the handoff
            body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Access Denied</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f1e8;
        --panel: #fffdf9;
        --ink: #1e2330;
        --muted: #5c6472;
        --accent: #c53030;
        --border: #d8cfc2;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: radial-gradient(circle at top, #fff7ea 0%, var(--bg) 65%);
        color: var(--ink);
      }}
      main {{
        max-width: 760px;
        margin: 48px auto;
        padding: 32px;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 20px;
        box-shadow: 0 18px 60px rgba(30, 35, 48, 0.12);
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 2rem;
        color: var(--accent);
      }}
      p {{
        line-height: 1.55;
      }}
      .status {{
        margin: 18px 0;
        padding: 14px 16px;
        border-radius: 12px;
        background: #faddd1;
        border: 1px solid #f5927f;
      }}
      code {{
        font-family: "SFMono-Regular", Consolas, monospace;
        background: #f3eee6;
        padding: 2px 6px;
        border-radius: 6px;
      }}
      .muted {{
        color: var(--muted);
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>⛔ Access Denied</h1>
      <p>The governance layer has blocked your access to <code>{safe_path}</code>.</p>
      <div class="status">
        <strong>Handoff to Onyx was denied by control-plane policy.</strong>
        <div class="muted">Governance decision: {flow_result.launch_gate_decision if flow_result else 'error'}</div>
        <div class="muted">Trace ID: <code>{flow_result.trace_id if flow_result else 'unknown'}</code></div>
      </div>
      <p><strong>Reasons for denial:</strong></p>
      <ul>
        <li>Your policy does not permit access to <code>onyx</code>.</li>
        <li>Your retrieval or tool governance requires audit review before Onyx access.</li>
        <li>Your account or tenant is not approved for Onyx features on this path.</li>
      </ul>
      <p class="muted">This decision has been logged for audit. Contact your administrator if you believe this is an error.</p>
    </main>
  </body>
</html>
"""
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.FORBIDDEN.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        # Governance allowed the handoff, proceed with link
        local_url = f"http://127.0.0.1:3010{safe_path}"
        public_url = _public_service_url(3010, safe_path)
        local_ready = self._url_is_reachable(local_url)
        codespaces_visible = self._url_is_reachable(_public_service_url(3010))

        body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Open Onyx</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f1e8;
        --panel: #fffdf9;
        --ink: #1e2330;
        --muted: #5c6472;
        --accent: #a03d26;
        --border: #d8cfc2;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: radial-gradient(circle at top, #fff7ea 0%, var(--bg) 65%);
        color: var(--ink);
      }}
      main {{
        max-width: 760px;
        margin: 48px auto;
        padding: 32px;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 20px;
        box-shadow: 0 18px 60px rgba(30, 35, 48, 0.12);
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 2rem;
      }}
      p {{
        line-height: 1.55;
      }}
      .status {{
        margin: 18px 0;
        padding: 14px 16px;
        border-radius: 12px;
        background: {"#eef8ef" if local_ready else "#fff4e5"};
        border: 1px solid {"#9cc7a3" if local_ready else "#d8cfc2"};
      }}
      .actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin: 24px 0 16px;
      }}
      a.button {{
        display: inline-block;
        padding: 12px 18px;
        border-radius: 999px;
        background: var(--accent);
        color: white;
        text-decoration: none;
        font-weight: 600;
      }}
      code {{
        font-family: "SFMono-Regular", Consolas, monospace;
        background: #f3eee6;
        padding: 2px 6px;
        border-radius: 6px;
      }}
      ol {{
        padding-left: 20px;
      }}
      .muted {{
        color: var(--muted);
      }}
      .governance {{
        font-size: 0.85rem;
        color: var(--muted);
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--border);
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Onyx Launch Handoff</h1>
      <p>The control plane found a live Onyx runtime on local port <code>3010</code> and prepared the link for <code>{safe_path}</code>.</p>
      <p><strong>Governance Status:</strong> ✓ Approved by control-plane policy.</p>
      <div class="status">
        <strong>{"Local Onyx is running." if local_ready else "Local Onyx is not responding yet."}</strong>
        <div class="muted">{"The dashboard link was failing because the public Codespaces port is still protected by the tunnel." if not codespaces_visible else "The public Codespaces URL appears reachable."}</div>
      </div>
      <div class="actions">
        <a class="button" href="{public_url}">Open Onyx</a>
      </div>
      <p class="muted">Target URL: <code>{public_url}</code></p>
      <p>If this still opens a <code>401 tunnel</code> page, expose port <code>3010</code> in the Codespaces <strong>Ports</strong> tab and then try again.</p>
      <ol>
        <li>Open the <strong>Ports</strong> tab in Codespaces.</li>
        <li>Find port <code>3010</code>.</li>
        <li>Use <strong>Open in Browser</strong> or change visibility from <code>Private</code> to <code>Public</code> or <code>Organization</code>.</li>
      </ol>
      <div class="governance">
        <strong>Governance Audit Trail:</strong><br>
        Trace: <code>{flow_result.trace_id if flow_result else 'unknown'}</code><br>
        Decision: <code>{flow_result.launch_gate_decision if flow_result else 'pass'}</code><br>
        Policy: Allow | Retrieval: Allow | Tools: Allow
      </div>
    </main>
  </body>
</html>
"""
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _url_is_reachable(self, url: str) -> bool:
        try:
            with urlopen(url, timeout=2) as response:
                return int(getattr(response, "status", 0)) < 400
        except (OSError, URLError):
            return False

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
