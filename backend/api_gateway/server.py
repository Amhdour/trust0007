from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import urlopen

from backend.integration_adapter import load_runtime_policy_bundle
from backend.posture_service.service import build_control_plane_dashboard, build_control_plane_live_log
from backend.governance_flow_evaluator import GovernedFlowEvaluator
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import PolicyDecision, RetrievalDecision, ToolDecision, NormalizedRequest
from adapters.retrieval.interfaces import RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.tools.interfaces import ToolExecutor
from adapters.tools.policy_model import StaticToolPolicyEvaluator, ToolPolicyConfig
from adapters.tools.schemas import ToolActionRequest


REPO_ROOT = Path(os.environ.get("CONTROL_PLANE_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
STATIC_ROOT = REPO_ROOT / "frontend/main-dashboard"
ARTIFACT_DIR = Path(
    os.environ.get(
        "CONTROL_PLANE_ARTIFACT_DIR",
        str(REPO_ROOT / "overlays" / "myStarterKit" / "artifacts"),
    )
).resolve()


@dataclass(frozen=True)
class RuntimePolicyContext:
    document: dict
    relative_path: str
    source: str


def _runtime_policy_context() -> RuntimePolicyContext:
    bundle = load_runtime_policy_bundle(REPO_ROOT)
    return RuntimePolicyContext(
        document=bundle.document,
        relative_path=bundle.relative_path,
        source=bundle.source,
    )


def _public_service_url(port: int, path: str = "") -> str:
    codespace_name = os.environ.get("CODESPACE_NAME", "").strip()
    forwarding_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "").strip()
    if codespace_name and forwarding_domain:
        base = f"https://{codespace_name}-{port}.{forwarding_domain}"
    else:
        base = f"http://localhost:{port}"
    return f"{base}{path}"


def _surface_rules(policy: dict) -> list[dict]:
    rules = list(policy.get("surfaces", {}).get("path_policies", []))
    return sorted(
        rules,
        key=lambda rule: (
            -len(str(rule.get("path", ""))),
            -len(rule.get("query", {}) or {}),
        ),
    )


def _resolve_surface(policy: dict, requested_path: str) -> dict:
    parsed = urlparse(requested_path)
    path = parsed.path or "/app"
    query = {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}

    for rule in _surface_rules(policy):
        if rule.get("path") != path:
            continue
        expected_query = rule.get("query", {}) or {}
        if any(query.get(key) != value for key, value in expected_query.items()):
            continue
        return {
            "surface": str(rule.get("surface", "")),
            "path": path,
            "query": query,
            "allowed_roles": list(rule.get("allowed_roles", [])),
        }

    return {
        "surface": "",
        "path": path,
        "query": query,
        "allowed_roles": [],
    }


class RuntimePolicyChecker(PolicyChecker):
    def __init__(self, policy_context: RuntimePolicyContext) -> None:
        self._context = policy_context
        self._policy = policy_context.document

    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        forbidden_terms = list(
            self._policy.get("content_rules", {}).get("forbidden_terms", ["hack", "exploit", "bypass"])
        )
        lowered_prompt = request.prompt.lower()
        if any(word.lower() in lowered_prompt for word in forbidden_terms):
            return PolicyDecision(allow=False, reasons=["policy.forbidden_content"])

        roles = list(request.metadata.get("identity_roles", []))
        allowed_tenant_roles = set(self._policy.get("identity", {}).get("tenant_roles", {}).get(request.tenant_id, []))
        if allowed_tenant_roles:
            invalid_roles = [role for role in roles if role not in allowed_tenant_roles]
            if invalid_roles:
                return PolicyDecision(
                    allow=False,
                    reasons=[f"policy.identity_role_not_allowed:{role}" for role in invalid_roles],
                )

        requested_path = str(request.metadata.get("requested_path", ""))
        if requested_path:
            surface_info = _resolve_surface(self._policy, requested_path)
            surface_name = surface_info.get("surface", "")
            if not surface_name:
                return PolicyDecision(allow=False, reasons=[f"policy.surface_not_registered:{surface_info['path']}"])

            allowed_roles = set(surface_info.get("allowed_roles", []))
            if allowed_roles and not any(role in allowed_roles for role in roles):
                return PolicyDecision(
                    allow=False,
                    reasons=[f"policy.surface_role_denied:{surface_name}"],
                )

        return PolicyDecision(
            allow=True,
            reasons=["policy.allow"],
        )


class RuntimeRetrievalChecker(RetrievalChecker):
    def __init__(self, policy_context: RuntimePolicyContext) -> None:
        self._policy = policy_context.document

    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        if not request.retrieval_needed:
            return RetrievalDecision(allow=True, reasons=["retrieval.not_needed"])

        tenant_sources = self._policy.get("retrieval", {}).get("tenant_allowed_sources", {}).get(request.tenant_id, [])
        if request.retrieval_source not in tenant_sources:
            return RetrievalDecision(
                allow=False,
                reasons=[f"retrieval.source_not_allowed:{request.retrieval_source or 'unknown'}"],
            )

        return RetrievalDecision(allow=True, reasons=["retrieval.allow"])


class RuntimeToolChecker(ToolDecisionChecker):
    def __init__(self, policy_context: RuntimePolicyContext) -> None:
        self._policy = policy_context.document

    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        tool_policy = self._policy.get("tools", {})
        allowed_tools = set(tool_policy.get("allowed_tools", []))
        allowed_tools.update(tool_policy.get("confirmation_required_tools", []))
        forbidden_tools = set(tool_policy.get("forbidden_tools", []))

        denied_tools = []
        reasons = []

        for tool in request.requested_tools:
            if tool in forbidden_tools:
                denied_tools.append(tool)
                reasons.append(f"tool.forbidden:{tool}")
            elif tool not in allowed_tools:
                denied_tools.append(tool)
                reasons.append(f"tool.not_allowed:{tool}")

        allowed_tools_list = [t for t in request.requested_tools if t not in denied_tools]

        return ToolDecision(allowed_tools=allowed_tools_list, denied_tools=denied_tools, reasons=reasons)


class SeedRetrievalBackend(RetrievalBackend):
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


class RuntimeRetrievalPolicy(RetrievalPolicyEvaluator):
    def __init__(self, policy_context: RuntimePolicyContext) -> None:
        self._policy = policy_context.document

    def evaluate(self, request: RetrievalRequest) -> dict:
        allowed_integrations = set(self._policy.get("integrations", {}).get("allowed_integrations", []))
        retrieval_policy = self._policy.get("retrieval", {})
        allowed_sources = retrieval_policy.get("tenant_allowed_sources", {}).get(request.tenant_id, [])
        required_trust_labels = retrieval_policy.get("source_trust_labels", {}).get(request.source, [])
        required_provenance_fields = retrieval_policy.get("required_provenance_fields", [])

        if f"retrieval.{request.source}" not in allowed_integrations:
            return {
                "allow": False,
                "mode": "deny",
                "reasons": [f"retrieval.integration_not_allowed:{request.source}"],
            }

        if not allowed_sources:
            return {
                "allow": False,
                "mode": "deny",
                "reasons": [f"retrieval.tenant_not_allowed:{request.tenant_id}"],
            }

        if request.source not in allowed_sources:
            return {
                "allow": False,
                "mode": "deny",
                "reasons": [f"retrieval.source_not_allowed:{request.source}"],
            }

        return {
            "allow": True,
            "mode": "allow",
            "reasons": [
                f"retrieval.integration_allowed:{request.source}",
                f"retrieval.tenant_scoped:{request.tenant_id}",
            ]
            + ([f"retrieval.trust_labels_required:{','.join(required_trust_labels)}"] if required_trust_labels else [])
            + ([f"retrieval.provenance_required:{','.join(required_provenance_fields)}"] if required_provenance_fields else []),
            "required_trust_labels": required_trust_labels,
            "required_provenance_fields": required_provenance_fields,
            "deny_on_empty_result": True,
        }


class RuntimeToolExecutor(ToolExecutor):
    def __init__(self, policy_context: RuntimePolicyContext) -> None:
        self._policy = policy_context.document

    def execute(self, request: ToolActionRequest) -> dict:
        tool_policy = self._policy.get("tools", {})
        allowed_tools = set(tool_policy.get("allowed_tools", []))
        confirmation_required = set(tool_policy.get("confirmation_required_tools", []))
        executable_tools = allowed_tools | confirmation_required

        if request.tool_name in confirmation_required and not request.confirmed:
            raise PermissionError(f"tool.confirmation_required:{request.tool_name}")

        if request.tool_name not in executable_tools:
            raise PermissionError(f"tool.execution_not_allowed:{request.tool_name}")

        return {
            "result": "executed",
            "tool": request.tool_name,
            "tenant_id": request.tenant_id,
            "governance_mode": "runtime_policy",
        }


def _runtime_tool_policy_config(policy_context: RuntimePolicyContext) -> ToolPolicyConfig:
    tool_policy = policy_context.document.get("tools", {})
    confirmation_required = set(tool_policy.get("confirmation_required_tools", []))
    argument_policies = tool_policy.get("argument_policies", {})
    return ToolPolicyConfig(
        tool_allowlist=set(tool_policy.get("allowed_tools", [])),
        confirmation_required_tools=confirmation_required,
        forbidden_tools=set(tool_policy.get("forbidden_tools", [])),
        forbidden_arguments={"password", "api_key", "token", "secret"},
        allowed_arguments_by_tool={
            tool_name: set(policy.get("allowed_arguments", []))
            for tool_name, policy in argument_policies.items()
            if policy.get("allowed_arguments") is not None
        },
        required_arguments_by_tool={
            tool_name: set(policy.get("required_arguments", []))
            for tool_name, policy in argument_policies.items()
        },
        forbidden_argument_value_substrings={
            tool_name: {
                arg_name: set(values)
                for arg_name, values in policy.get("forbidden_value_substrings", {}).items()
            }
            for tool_name, policy in argument_policies.items()
        },
        high_risk_tools=confirmation_required,
        rate_limit_hints={tool: "approval_required" for tool in confirmation_required},
    )


def _artifact_list_markup(artifacts: dict[str, str]) -> str:
    if not artifacts:
        return "<li>No evaluator artifacts were generated.</li>"

    items = []
    for label, relative_path in artifacts.items():
        href = f"/raw/{quote(relative_path)}"
        items.append(f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a>: <code>{escape(relative_path)}</code></li>')
    return "".join(items)


def _build_governed_flow_evaluator(policy_context: RuntimePolicyContext) -> GovernedFlowEvaluator:
    return GovernedFlowEvaluator(
        policy_checker=RuntimePolicyChecker(policy_context),
        retrieval_checker=RuntimeRetrievalChecker(policy_context),
        tool_checker=RuntimeToolChecker(policy_context),
        retrieval_backend=SeedRetrievalBackend(),
        retrieval_policy=RuntimeRetrievalPolicy(policy_context),
        tool_executor=RuntimeToolExecutor(policy_context),
        tool_policy_evaluator=StaticToolPolicyEvaluator(_runtime_tool_policy_config(policy_context)),
        artifact_dir=ARTIFACT_DIR,
    )


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
        """Execute a governed flow with runtime policy enforcement and emit artifacts."""
        try:
            policy_context = _runtime_policy_context()
            evaluator = _build_governed_flow_evaluator(policy_context)

            result = evaluator.run(
                user_id="api-user",
                tenant_id="tenant-a",
                prompt="Demonstrate governed flow through control plane API",
                requested_tools=["search", "summarize"],
                retrieval_source="qdrant",
                retrieval_needed=True,
                roles=["tenant_user"],
                request_metadata={"surface": "control-plane.governed-flow"},
                tool_arguments={
                    "search": {"query": "Demonstrate governed flow through control plane API"},
                    "summarize": {"query": "Demonstrate governed flow through control plane API"},
                },
                policy_source=policy_context.source,
                policy_path=policy_context.relative_path,
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
        safe_path_html = escape(safe_path)
        flow_result = None
        error_reason = None

        # Run governance check for Onyx handoff
        try:
            policy_context = _runtime_policy_context()
            surface_info = _resolve_surface(policy_context.document, safe_path)
            evaluator = _build_governed_flow_evaluator(policy_context)

            flow_result = evaluator.run(
                user_id="dashboard-user",
                tenant_id="tenant-dashboard",
                prompt=f"Navigate to Onyx path: {safe_path}",
                requested_tools=["onyx"],
                retrieval_source="qdrant",
                retrieval_needed=False,
                roles=["tenant_user"],
                request_metadata={
                    "requested_path": safe_path,
                    "surface": surface_info.get("surface", ""),
                    "surface_query": surface_info.get("query", {}),
                },
                tool_arguments={
                    "onyx": {
                        "surface": surface_info.get("surface", ""),
                        "path": surface_info.get("path", safe_path),
                        "chat_mode": surface_info.get("query", {}).get("chatMode", ""),
                    }
                },
                policy_source=policy_context.source,
                policy_path=policy_context.relative_path,
            )
        except Exception as e:
            error_reason = f"{type(e).__name__}: {e}"

        # Determine if handoff is allowed
        governance_allowed = flow_result.decision if flow_result else False

        if not governance_allowed:
            denial_reasons = [escape(reason) for reason in (flow_result.reasons if flow_result else [f"Evaluator error: {error_reason or 'governance check failed'}"])]
            artifact_markup = _artifact_list_markup(flow_result.artifacts if flow_result else {})
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
      <p>The governance layer has blocked your access to <code>{safe_path_html}</code>.</p>
      <div class="status">
        <strong>Handoff to Onyx was denied by control-plane policy.</strong>
        <div class="muted">Governance decision: {flow_result.launch_gate_decision if flow_result else 'error'}</div>
        <div class="muted">Trace ID: <code>{flow_result.trace_id if flow_result else 'unknown'}</code></div>
        <div class="muted">Policy source: <code>{escape(flow_result.policy_source if flow_result else 'unknown')}</code> via <code>{escape(flow_result.policy_path if flow_result else 'unknown')}</code></div>
      </div>
      <p><strong>Reasons for denial:</strong></p>
      <ul>
        {"".join(f"<li>{reason}</li>" for reason in denial_reasons)}
      </ul>
      <p><strong>Evidence generated for this decision:</strong></p>
      <ul>
        {artifact_markup}
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
      <p>The control plane found a live Onyx runtime on local port <code>3010</code> and prepared the link for <code>{safe_path_html}</code>.</p>
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
        Policy Source: <code>{escape(flow_result.policy_source if flow_result else 'unknown')}</code> via <code>{escape(flow_result.policy_path if flow_result else 'unknown')}</code><br>
        Policy: {"Allow" if flow_result and flow_result.policy_allow else "Deny"} |
        Retrieval: {"Allow" if flow_result and flow_result.retrieval_allow else "Deny"} |
        Tools: {"Allow" if flow_result and not flow_result.denied_tools else "Deny"}<br>
        Reasons: <code>{escape(", ".join(flow_result.reasons) if flow_result and flow_result.reasons else "policy.allow")}</code><br>
        Evidence:
        <ul>
          {_artifact_list_markup(flow_result.artifacts if flow_result else {})}
        </ul>
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
