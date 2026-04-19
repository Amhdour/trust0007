from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
import mimetypes
import os
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import urlopen

from adapters.identity.keycloak import KeycloakIdentityProvider
from backend.activity_service.service import build_onyx_runtime_proof, build_onyx_workspace_activity
from backend.integration_adapter import load_runtime_policy_bundle
from backend.integration_adapter.repository import load_upstream_usage_inventory
from backend.posture_service.service import build_control_plane_dashboard, build_control_plane_live_log
from backend.governance_flow_evaluator import GovernedFlowEvaluator
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import PolicyDecision, RetrievalDecision, ToolDecision, NormalizedRequest
from adapters.policy.opa import OPAClient, OPAPolicyChecker
from adapters.retrieval.interfaces import RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.qdrant import QdrantRetrievalBackend
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.secrets.provider import VaultSecretsProvider
from adapters.secrets.vault import VaultHTTPClient
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


def _is_static_candidate(path: Path) -> bool:
    return path.exists() and path.is_file() and (STATIC_ROOT in path.parents or path == STATIC_ROOT / "index.html")


def _resolve_static_path(request_path: str) -> Path:
    if request_path in {"", "/"}:
        return STATIC_ROOT / "index.html"

    relative_path = request_path.lstrip("/")
    raw_candidate = (STATIC_ROOT / relative_path).resolve()
    candidates = [raw_candidate]

    if not Path(relative_path).suffix:
        candidates.append((STATIC_ROOT / f"{relative_path}.html").resolve())
        candidates.append((STATIC_ROOT / relative_path / "index.html").resolve())

    for candidate in candidates:
        if _is_static_candidate(candidate):
            return candidate

    return STATIC_ROOT / "index.html"


@dataclass(frozen=True)
class RuntimePolicyContext:
    document: dict
    relative_path: str
    source: str


@dataclass(frozen=True)
class RuntimeTarget:
    key: str
    label: str
    runtime_class: str
    default_path: str
    tool_name: str
    secret_path_suffix: str
    port_env_var: str
    default_port: int


RUNTIME_REGISTRY: dict[str, RuntimeTarget] = {
    "onyx": RuntimeTarget(
        key="onyx",
        label="Onyx",
        runtime_class="rag",
        default_path="/app",
        tool_name="onyx",
        secret_path_suffix="onyx",
        port_env_var="CONTROL_PLANE_ONYX_PORT",
        default_port=3010,
    ),
    "dify": RuntimeTarget(
        key="dify",
        label="Dify",
        runtime_class="autonomous_agents",
        default_path="/apps",
        tool_name="dify",
        secret_path_suffix="dify",
        port_env_var="CONTROL_PLANE_DIFY_PORT",
        default_port=8088,
    ),
}


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


def _runtime_target(runtime_key: str) -> RuntimeTarget:
    return RUNTIME_REGISTRY.get(runtime_key.strip().lower(), RUNTIME_REGISTRY["onyx"])


def _runtime_port(target: RuntimeTarget) -> int:
    try:
        return int(os.environ.get(target.port_env_var, str(target.default_port)))
    except ValueError:
        return target.default_port


def _governance_mode(explicit: str = "") -> str:
    return (explicit or os.environ.get("CONTROL_PLANE_GOVERNANCE_MODE", "demo")).strip().lower() or "demo"


def _control_plane_environment_mode() -> str:
    return os.environ.get("CONTROL_PLANE_ENVIRONMENT_MODE", "dev").strip().lower() or "dev"


def _is_local_url(url: str) -> bool:
    lowered = url.strip().lower()
    return any(token in lowered for token in ("localhost", "127.0.0.1", "0.0.0.0"))


def _validate_startup_configuration() -> None:
    governance_mode = _governance_mode()
    environment_mode = _control_plane_environment_mode()
    live_like_environment = environment_mode in {"staging", "stage", "production", "prod", "live"}
    errors: list[str] = []

    if governance_mode == "live" and environment_mode in {"dev", "local"}:
        errors.append("startup.environment_mode_dev_not_allowed_for_live_governance")
    if live_like_environment and governance_mode != "live":
        errors.append("startup.governance_mode_must_be_live_for_staging_or_production")

    keycloak_dev_mode = os.environ.get("CONTROL_PLANE_KEYCLOAK_DEV_MODE", "").strip().lower() in {"1", "true", "yes"}
    vault_dev_mode = os.environ.get("CONTROL_PLANE_VAULT_DEV_MODE", "").strip().lower() in {"1", "true", "yes"}
    if live_like_environment and keycloak_dev_mode:
        errors.append("startup.keycloak_dev_mode_not_allowed")
    if live_like_environment and vault_dev_mode:
        errors.append("startup.vault_dev_mode_not_allowed")

    if governance_mode == "live":
        required_env = [
            "CONTROL_PLANE_VAULT_TOKEN",
            "CONTROL_PLANE_KEYCLOAK_BASE_URL",
            "CONTROL_PLANE_OPA_URL",
            "CONTROL_PLANE_QDRANT_URL",
            "CONTROL_PLANE_ONYX_SECRET_PATH",
            "CONTROL_PLANE_DIFY_SECRET_PATH",
        ]
        for env_name in required_env:
            if not os.environ.get(env_name, "").strip():
                errors.append(f"startup.missing_required_env:{env_name}")
        if not os.environ.get("CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS", "").strip():
            errors.append("startup.missing_required_env:CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS")

    allow_local_targets = os.environ.get("CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    externally_reachable = os.environ.get("CONTROL_PLANE_EXTERNAL_REACHABLE", "false").strip().lower() in {"1", "true", "yes"}
    if governance_mode == "live" and externally_reachable and not allow_local_targets:
        for target in RUNTIME_REGISTRY.values():
            runtime_url = _public_service_url(_runtime_port(target))
            if _is_local_url(runtime_url):
                errors.append(f"startup.local_runtime_target_not_allowed:{target.key}")

    if errors:
        raise RuntimeError("Live configuration validation failed: " + ", ".join(errors))


def _keycloak_userinfo_url() -> str:
    explicit = os.environ.get("CONTROL_PLANE_KEYCLOAK_USERINFO_URL", "").strip()
    if explicit:
        return explicit
    base_url = os.environ.get("CONTROL_PLANE_KEYCLOAK_BASE_URL", "http://keycloak:8080").strip().rstrip("/")
    realm = os.environ.get("CONTROL_PLANE_KEYCLOAK_REALM", "umbrella-dev").strip()
    return f"{base_url}/realms/{realm}/protocol/openid-connect/userinfo"


def _default_tenant_id() -> str:
    return os.environ.get("CONTROL_PLANE_DEFAULT_TENANT_ID", "tenant-a").strip() or "tenant-a"


def _dashboard_user_id() -> str:
    return os.environ.get("CONTROL_PLANE_DASHBOARD_USER_ID", "dashboard-user").strip() or "dashboard-user"


def _governed_flow_user_id() -> str:
    return os.environ.get("CONTROL_PLANE_API_USER_ID", "api-user").strip() or "api-user"


def _onyx_secret_path(tenant_id: str = "") -> str:
    explicit = os.environ.get("CONTROL_PLANE_ONYX_SECRET_PATH", "").strip()
    if explicit:
        return explicit
    resolved_tenant = tenant_id or _default_tenant_id()
    return f"secret/data/runtime/{resolved_tenant}/onyx"


def _required_secret_path(tenant_id: str = "") -> str:
    explicit = os.environ.get("CONTROL_PLANE_REQUIRED_SECRET_PATH", "").strip()
    if explicit:
        return explicit
    resolved_tenant = tenant_id or _default_tenant_id()
    return f"secret/data/runtime/{resolved_tenant}/governed-flow"


def _runtime_secret_path(target: RuntimeTarget, tenant_id: str = "") -> str:
    env_var = f"CONTROL_PLANE_{target.key.upper()}_SECRET_PATH"
    explicit = os.environ.get(env_var, "").strip()
    if explicit:
        return explicit
    resolved_tenant = tenant_id or _default_tenant_id()
    return f"secret/data/runtime/{resolved_tenant}/{target.secret_path_suffix}"


def _cookie_map(raw_cookie: str) -> dict[str, str]:
    cookie = SimpleCookie()
    cookie.load(raw_cookie or "")
    return {name: morsel.value for name, morsel in cookie.items()}


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


def _runtime_controls(policy: dict, runtime_key: str) -> dict:
    controls = policy.get("runtime_controls", {})
    runtime = controls.get(runtime_key, {})
    return runtime if isinstance(runtime, dict) else {}


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
        runtime_key = str(request.metadata.get("runtime_key", "onyx") or "onyx")
        runtime_controls = _runtime_controls(self._policy, runtime_key)
        if not runtime_controls:
            return PolicyDecision(allow=False, reasons=[f"policy.runtime_not_configured:{runtime_key}"])

        if runtime_key == "onyx" and bool(runtime_controls.get("require_data_boundary", False)):
            tenant_sources = self._policy.get("retrieval", {}).get("tenant_allowed_sources", {}).get(request.tenant_id, [])
            if not tenant_sources:
                return PolicyDecision(allow=False, reasons=[f"policy.data_boundary_not_configured:{request.tenant_id}"])

        if runtime_key == "dify" and bool(runtime_controls.get("require_mcp_governance", False)):
            allowed_mcp_servers = set(runtime_controls.get("mcp_allowed_servers", []))
            if not allowed_mcp_servers:
                return PolicyDecision(allow=False, reasons=["policy.mcp_not_configured:dify"])
            requested_mcp_server = str(request.metadata.get("requested_mcp_server", "")).strip()
            if requested_mcp_server and requested_mcp_server not in allowed_mcp_servers:
                return PolicyDecision(allow=False, reasons=[f"policy.mcp_server_not_allowed:{requested_mcp_server}"])

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
    dify_controls = _runtime_controls(policy_context.document, "dify")
    confirmation_required.update(dify_controls.get("approval_required_tools", []))
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _artifact_relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_json_array(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _runtime_reachability_summary(
    *,
    runtime_label: str,
    governance_allowed: bool,
    local_ready: bool | None,
    public_ready: bool | None,
    local_url: str,
    public_url: str,
) -> dict[str, object]:
    if not governance_allowed:
        status = "blocked_before_runtime"
        label = "Blocked before runtime"
        detail = f"Governance denied the handoff before the control plane could rely on {runtime_label} runtime availability."
    elif local_ready and public_ready:
        status = "local_and_public_ready"
        label = "Local + public reachable"
        detail = f"The governed target is reachable from the local {runtime_label} runtime and from the public handoff URL."
    elif local_ready:
        status = "local_ready_public_pending"
        label = "Local reachable, public pending"
        detail = f"The local {runtime_label} runtime is up, but the public tunnel still needs attention before outside browser access will work cleanly."
    elif public_ready:
        status = "public_visible_local_unhealthy"
        label = "Public visible, local unhealthy"
        detail = f"The public URL responds, but the local {runtime_label} runtime behind it is not healthy yet."
    else:
        status = "runtime_unreachable"
        label = "Runtime not reachable"
        detail = f"Governance approved the handoff, but the configured {runtime_label} runtime is not responding yet."
    return {
        "status": status,
        "label": label,
        "detail": detail,
        "local_url": local_url,
        "public_url": public_url,
        "local_ready": bool(local_ready),
        "public_ready": bool(public_ready),
    }


def _sync_runtime_proof_refs(trace_id: str, proof: dict, refs: dict[str, str], *, artifact_key: str, runtime_key: str) -> None:
    runtime_summary = {
        "runtime_key": str(proof.get("runtime_key", runtime_key)),
        "runtime_label": str(proof.get("runtime_label", "")),
        "runtime_class": str(proof.get("runtime_class", "")),
        "captured_at": str(proof.get("generated_at", "")),
        "artifact": refs.get("latest", ""),
        "canonical_artifact": refs.get("canonical", refs.get("latest", "")),
        "history_artifact": refs.get("history", refs.get("latest", "")),
        "requested_path": str(proof.get("requested_path", "")),
        "handoff_allowed": bool(proof.get("handoff_allowed", False)),
        "evidence_mode": str(proof.get("evidence_mode", "")),
        "policy_source": str(proof.get("policy_source", "")),
        "policy_path": str(proof.get("policy_path", "")),
        "reachability": dict(proof.get("reachability", {})),
        "continuity": dict(proof.get("continuity", {})),
        "latest_activity": dict(proof.get("latest_activity", {})),
        "matched_activity": dict(proof.get("matched_activity", {})),
    }

    summary_paths = [
        ARTIFACT_DIR / "governed-flow-summary.json",
        ARTIFACT_DIR / "governed-request-history" / trace_id / "governed-flow-summary.json",
    ]
    for summary_path in summary_paths:
        if not summary_path.exists():
            continue
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        if trace_id and str(payload.get("trace_id", "")) not in {"", trace_id}:
            continue
        payload["runtime_proof"] = runtime_summary
        runtime_proofs = dict(payload.get("runtime_proofs", {}))
        runtime_proofs[runtime_key] = runtime_summary
        payload["runtime_proofs"] = runtime_proofs
        _write_json(summary_path, payload)

    feed_path = ARTIFACT_DIR / "governed-request-feed.json"
    feed = _load_json_array(feed_path)
    if not feed:
        return
    updated = False
    for item in feed:
        if str(item.get("trace_id", "")) != trace_id:
            continue
        artifact_refs = dict(item.get("artifact_refs", {}))
        artifact_refs[artifact_key] = refs.get("history", refs.get("latest", ""))
        item["artifact_refs"] = artifact_refs
        item["runtime_proof"] = runtime_summary
        runtime_proofs = dict(item.get("runtime_proofs", {}))
        runtime_proofs[runtime_key] = runtime_summary
        item["runtime_proofs"] = runtime_proofs
        updated = True
    if updated:
        _write_json(feed_path, feed)


def _record_runtime_proof(
    *,
    target: RuntimeTarget,
    requested_path: str,
    governance_allowed: bool,
    flow_result: GovernedFlowEvaluator | object | None,
    flow_mode: str,
    local_ready: bool | None,
    public_ready: bool | None,
    local_url: str,
    public_url: str,
) -> dict:
    trace_id = str(getattr(flow_result, "trace_id", "") if flow_result else "")
    session_id = str(getattr(flow_result, "session_id", "") if flow_result else "")
    if target.key == "onyx":
        proof = build_onyx_runtime_proof(
            REPO_ROOT,
            requested_path=requested_path,
            trace_id=trace_id,
            session_id=session_id,
        )
    else:
        proof = {
            "requested_path": requested_path,
            "trace_id": trace_id,
            "session_id": session_id,
            "continuity": {
                "status": "runtime_activity_observed" if governance_allowed else "blocked_before_runtime",
                "label": "Runtime continuity observed" if governance_allowed else "Blocked before runtime",
                "detail": (
                    f"Governed {target.label} handoff approved; continuity is currently inferred from handoff telemetry."
                    if governance_allowed
                    else f"Governed {target.label} handoff was denied before runtime continuity checks."
                ),
            },
            "latest_activity": {
                "summary": (
                    f"Latest governed {target.label} handoff event recorded."
                    if governance_allowed
                    else f"No governed {target.label} runtime activity because handoff was denied."
                )
            },
            "matched_activity": {},
        }
    runtime_artifact = f"{target.key}-runtime-proof.json"
    latest_path = ARTIFACT_DIR / runtime_artifact
    canonical_latest_path = ARTIFACT_DIR / "runtime-proof.json"
    history_path = ARTIFACT_DIR / "governed-request-history" / trace_id / runtime_artifact if trace_id else None
    refs = {
        "latest": _artifact_relative_path(latest_path),
        "canonical": _artifact_relative_path(canonical_latest_path),
        "history": _artifact_relative_path(history_path) if history_path else _artifact_relative_path(latest_path),
    }
    proof.update(
        {
            "artifact": refs["latest"],
            "canonical_artifact": refs["canonical"],
            "history_artifact": refs["history"],
            "handoff_allowed": governance_allowed,
            "evidence_mode": str(getattr(flow_result, "evidence_mode", flow_mode) if flow_result else flow_mode),
            "launch_gate_decision": str(getattr(flow_result, "launch_gate_decision", "") if flow_result else ""),
            "policy_source": str(getattr(flow_result, "policy_source", "") if flow_result else ""),
            "policy_path": str(getattr(flow_result, "policy_path", "") if flow_result else ""),
            "runtime_key": target.key,
            "runtime_label": target.label,
            "runtime_class": target.runtime_class,
            "reachability": _runtime_reachability_summary(
                runtime_label=target.label,
                governance_allowed=governance_allowed,
                local_ready=local_ready,
                public_ready=public_ready,
                local_url=local_url,
                public_url=public_url,
            ),
        }
    )
    _write_json(latest_path, proof)
    _write_json(canonical_latest_path, proof)
    if history_path:
        _write_json(history_path, proof)
        _sync_runtime_proof_refs(
            trace_id,
            proof,
            refs,
            artifact_key=f"{target.key}_runtime_proof",
            runtime_key=target.key,
        )
    return proof


def _runtime_proof_markup(runtime_proof: dict) -> str:
    continuity = dict(runtime_proof.get("continuity", {}))
    reachability = dict(runtime_proof.get("reachability", {}))
    latest_activity = dict(runtime_proof.get("matched_activity") or runtime_proof.get("latest_activity") or {})
    runtime_label = str(runtime_proof.get("runtime_label", "Runtime"))
    latest_summary = str(latest_activity.get("summary", "")) or f"No recent {runtime_label} runtime activity captured yet."
    latest_timestamp = str(latest_activity.get("timestamp", ""))
    latest_activity_markup = escape(latest_summary)
    if latest_timestamp:
        latest_activity_markup = f"{latest_activity_markup} <span class=\"muted\">at <code>{escape(latest_timestamp)}</code></span>"
    artifact_ref = str(runtime_proof.get("artifact", ""))
    artifact_link = f"/raw/{quote(artifact_ref)}" if artifact_ref else ""
    artifact_markup = (
        f'<div class="muted">Proof artifact: <a href="{escape(artifact_link, quote=True)}"><code>{escape(artifact_ref)}</code></a></div>'
        if artifact_ref
        else ""
    )
    return f"""
      <div class="status">
        <strong>Runtime proof after handoff</strong>
        <div class="muted">Reachability: <code>{escape(str(reachability.get("label", "Unavailable")))}</code></div>
        <div class="muted">Continuity: <code>{escape(str(continuity.get("label", "Unavailable")))}</code></div>
        <div class="muted">{escape(str(continuity.get("detail", "")))}</div>
        <div class="muted">Latest {escape(runtime_label)} activity: {latest_activity_markup}</div>
        {artifact_markup}
      </div>
"""


def _workspace_activity_entry_markup(entry: dict) -> str:
    meta_bits: list[str] = []
    if entry.get("path_match"):
        meta_bits.append('<span class="activity-entry-chip activity-entry-chip-match">path match</span>')
    if entry.get("trace_match"):
        meta_bits.append('<span class="activity-entry-chip activity-entry-chip-match">trace match</span>')
    if entry.get("session_match"):
        meta_bits.append('<span class="activity-entry-chip activity-entry-chip-match">session match</span>')
    if entry.get("source_label"):
        meta_bits.append(f'<span class="activity-entry-chip">{escape(str(entry.get("source_label", "")))}</span>')
    if entry.get("trace_id"):
        meta_bits.append(
            f'<span class="activity-entry-chip">trace <code>{escape(str(entry.get("trace_id", "")))}</code></span>'
        )
    if entry.get("session_id"):
        meta_bits.append(
            f'<span class="activity-entry-chip">session <code>{escape(str(entry.get("session_id", "")))}</code></span>'
        )

    return f"""
      <article class="activity-entry activity-entry-{escape(str(entry.get("scope", "other")), quote=True)}">
        <div class="activity-entry-head">
          <strong>{escape(str(entry.get("summary", "")) or "Activity captured")}</strong>
          <span class="activity-entry-time">{escape(str(entry.get("timestamp", "")) or "Timestamp unavailable")}</span>
        </div>
        <p class="activity-entry-detail">{escape(str(entry.get("correlation_detail", "")))}</p>
        <div class="activity-entry-meta">
          {''.join(meta_bits)}
        </div>
      </article>
"""


def _workspace_activity_panel_markup(activity_payload: dict) -> str:
    counts = dict(activity_payload.get("counts", {}))
    groups = list(activity_payload.get("groups", []))
    limitations = list(activity_payload.get("limitations", []))
    summary = dict(activity_payload.get("summary", {}))
    source_href = str(activity_payload.get("source_href", ""))
    source_link = (
        f'<a class="activity-panel-link" href="{escape(source_href, quote=True)}">Open activity API</a>'
        if source_href
        else ""
    )

    groups_markup = "".join(
        f"""
      <section class="activity-group">
        <div class="activity-group-head">
          <div>
            <h3>{escape(str(group.get("title", "Activity")))}</h3>
            <p>{escape(str(group.get("description", "")))}</p>
          </div>
          <span class="activity-group-count">{len(group.get("entries", []))}</span>
        </div>
        {
            ''.join(_workspace_activity_entry_markup(entry) for entry in group.get('entries', []))
            if group.get('entries')
            else f'<div class="activity-group-empty">{escape(str(group.get("empty_state", "No activity captured.")))}</div>'
        }
      </section>
"""
        for group in groups
    )

    limitations_markup = "".join(f"<li>{escape(str(item))}</li>" for item in limitations)
    return f"""
      <section class="activity-panel-shell">
        <div class="activity-panel-head">
          <div>
            <p class="eyebrow">Current Onyx activity</p>
            <h2>Current Onyx Activity</h2>
            <p class="activity-panel-summary">{escape(str(summary.get("detail", "")))}</p>
          </div>
          <div class="activity-panel-summary-badge activity-panel-summary-{escape(str(summary.get("status", "neutral")), quote=True)}">
            {escape(str(summary.get("label", "Activity")))}
          </div>
        </div>
        <div class="activity-panel-chips">
          <span class="activity-panel-chip">direct path matches <strong>{escape(str(counts.get("current_surface", 0)))}</strong></span>
          <span class="activity-panel-chip">correlated trace/session <strong>{escape(str(counts.get("correlated", 0)))}</strong></span>
          <span class="activity-panel-chip">other runtime <strong>{escape(str(counts.get("other_runtime", 0)))}</strong></span>
          <span class="activity-panel-chip">Onyx source <strong>{escape(str(activity_payload.get("sources", {}).get("onyx", "unknown")))}</strong></span>
          <span class="activity-panel-chip">Langfuse source <strong>{escape(str(activity_payload.get("sources", {}).get("langfuse", "unknown")))}</strong></span>
        </div>
        <div class="activity-panel-groups">
          {groups_markup}
        </div>
        <div class="activity-panel-footer">
          <div>
            <strong>Limits of correlation</strong>
            <ul class="activity-panel-limitations">
              {limitations_markup}
            </ul>
          </div>
          {source_link}
        </div>
      </section>
"""


def _build_secret_provider() -> VaultSecretsProvider | None:
    vault_addr = os.environ.get("CONTROL_PLANE_VAULT_ADDR", "http://vault:8200").strip()
    vault_token = os.environ.get("CONTROL_PLANE_VAULT_TOKEN", "").strip()
    if not vault_addr or not vault_token:
        return None
    return VaultSecretsProvider(VaultHTTPClient(base_url=vault_addr, token=vault_token))


def _build_governed_flow_evaluator(policy_context: RuntimePolicyContext, *, flow_mode: str) -> GovernedFlowEvaluator:
    if flow_mode == "live":
        policy_checker: PolicyChecker = OPAPolicyChecker(
            client=OPAClient(os.environ.get("CONTROL_PLANE_OPA_URL", "http://opa:8181")),
            package_path=os.environ.get("CONTROL_PLANE_OPA_PACKAGE", "umbrella/policy/decision"),
            runtime_policy=policy_context.document,
            environment_mode=_control_plane_environment_mode(),
        )
        retrieval_backend: RetrievalBackend = QdrantRetrievalBackend(
            base_url=os.environ.get("CONTROL_PLANE_QDRANT_URL", "http://qdrant:6333"),
            collection=os.environ.get("CONTROL_PLANE_QDRANT_COLLECTION", "governed_docs"),
        )
        identity_provider = KeycloakIdentityProvider(_keycloak_userinfo_url())
        secret_provider = _build_secret_provider()
    else:
        policy_checker = RuntimePolicyChecker(policy_context)
        retrieval_backend = SeedRetrievalBackend()
        identity_provider = None
        secret_provider = None

    return GovernedFlowEvaluator(
        policy_checker=policy_checker,
        retrieval_checker=RuntimeRetrievalChecker(policy_context),
        tool_checker=RuntimeToolChecker(policy_context),
        retrieval_backend=retrieval_backend,
        retrieval_policy=RuntimeRetrievalPolicy(policy_context),
        tool_executor=RuntimeToolExecutor(policy_context),
        tool_policy_evaluator=StaticToolPolicyEvaluator(_runtime_tool_policy_config(policy_context)),
        artifact_dir=ARTIFACT_DIR,
        identity_provider=identity_provider,
        secret_provider=secret_provider,
        flow_mode=flow_mode,
        environment_mode=_control_plane_environment_mode(),
    )


def _dependency_summary_markup(flow_result: GovernedFlowEvaluator | object | None) -> str:
    if flow_result is None or not hasattr(flow_result, "dependency_status"):
        return "<li>Dependency status unavailable.</li>"
    dependency_status = getattr(flow_result, "dependency_status", {}) or {}
    items = []
    for name, payload in dependency_status.items():
        if not isinstance(payload, dict):
            continue
        status_bits = []
        for key in ("mandatory", "live", "authenticated", "allow", "live_backend", "fetched", "complete", "source", "engine", "reason"):
            value = payload.get(key)
            if value in {"", None}:
                continue
            status_bits.append(f"{escape(str(key))}={escape(str(value))}")
        items.append(f"<li><strong>{escape(str(name))}</strong>: {', '.join(status_bits) if status_bits else 'status unavailable'}</li>")
    return "".join(items) or "<li>Dependency status unavailable.</li>"


class ControlPlaneRequestHandler(BaseHTTPRequestHandler):
    server_version = "control-plane/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(getattr(self, "path", "/"))
        path = parsed.path

        if path in {"/api/health", "/healthz"}:
            self._send_json({"status": "ok"})
            return

        if path in {"/api/control-plane", "/api/control-plane/overview"}:
            self._send_json(build_control_plane_dashboard(REPO_ROOT))
            return

        if path == "/api/control-plane/upstream-usage":
            self._send_json(load_upstream_usage_inventory(REPO_ROOT))
            return

        if path == "/api/control-plane/live-log":
            limit = self._parse_int_query(parse_qs(parsed.query).get("limit", ["12"])[0], default=12, minimum=1, maximum=50)
            self._send_json(build_control_plane_live_log(REPO_ROOT, limit=limit))
            return

        if path == "/api/control-plane/onyx-activity":
            query = parse_qs(parsed.query)
            limit = self._parse_int_query(self._query_value(query, "limit", "6"), default=6, minimum=1, maximum=12)
            activity_payload = build_onyx_workspace_activity(
                REPO_ROOT,
                requested_path=self._query_value(query, "path", "/app"),
                trace_id=self._query_value(query, "trace_id", ""),
                session_id=self._query_value(query, "session_id", ""),
                limit=limit,
            )
            if self._query_value(query, "format", "").lower() == "html":
                self._send_html(_workspace_activity_panel_markup(activity_payload))
            else:
                self._send_json(activity_payload)
            return

        if path == "/api/control-plane/governed-flow":
            self._handle_governed_flow()
            return

        if path.startswith("/raw/"):
            self._serve_repo_file(path.removeprefix("/raw/"))
            return

        if path.startswith("/launch/"):
            runtime_key = path.removeprefix("/launch/").strip().lower()
            if runtime_key in RUNTIME_REGISTRY:
                requested_path = parse_qs(parsed.query).get("path", [RUNTIME_REGISTRY[runtime_key].default_path])[0]
                self._serve_runtime_handoff(requested_path, runtime=runtime_key)
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

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK, *, cookies: list[str] | None = None) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status.value)
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(self, location: str, *, cookies: list[str] | None = None, status: HTTPStatus = HTTPStatus.SEE_OTHER) -> None:
        self.send_response(status.value)
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _parse_int_query(self, raw_value: str, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(raw_value)
        except ValueError:
            return default
        return max(minimum, min(maximum, parsed))

    def _query_value(self, query: dict[str, list[str]], key: str, default: str = "") -> str:
        values = query.get(key, [])
        return values[-1] if values else default

    def _request_cookies(self) -> dict[str, str]:
        return _cookie_map(self.headers.get("Cookie", ""))

    def _handle_governed_flow(self) -> None:
        """Execute a governed flow with runtime policy enforcement and emit artifacts."""
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            flow_mode = _governance_mode(self._query_value(query, "mode", ""))
            secret_required = self._query_value(query, "secret_required", "").lower() in {"1", "true", "yes"}
            question = self._query_value(query, "question", "Demonstrate governed flow through control plane API")
            policy_context = _runtime_policy_context()
            evaluator = _build_governed_flow_evaluator(policy_context, flow_mode=flow_mode)
            tenant_id = _default_tenant_id()

            result = evaluator.run(
                user_id=_governed_flow_user_id(),
                tenant_id=tenant_id,
                prompt=question,
                requested_tools=["search", "summarize"],
                retrieval_source="qdrant",
                retrieval_needed=True,
                roles=["tenant_user"],
                request_metadata={
                    "surface": "control-plane.governed-flow",
                    "requested_path": "/app?chatMode=search",
                },
                tool_arguments={
                    "search": {"query": question},
                    "summarize": {"query": question},
                },
                policy_source=policy_context.source,
                policy_path=policy_context.relative_path,
                authorization_header=self.headers.get("Authorization", ""),
                cookies=self._request_cookies(),
                evidence_mode=flow_mode,
                secret_request={
                    "needed": secret_required,
                    "secret_path": _required_secret_path(tenant_id),
                    "secret_key": os.environ.get("CONTROL_PLANE_REQUIRED_SECRET_KEY", "api_token"),
                    "purpose": "governed_flow_runtime_secret",
                }
                if secret_required
                else None,
            )

            self._send_json(result.to_dict())
        except Exception as e:
            self._send_json(
                {"error": str(e), "type": type(e).__name__},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _serve_static(self, request_path: str) -> None:
        self._send_file(_resolve_static_path(request_path))

    def _serve_repo_file(self, relative_path: str) -> None:
        candidate = (REPO_ROOT / unquote(relative_path)).resolve()
        if not candidate.exists() or not candidate.is_file() or REPO_ROOT not in candidate.parents:
            self.send_error(HTTPStatus.NOT_FOUND.value, "File not found")
            return
        self._send_file(candidate)

    def _serve_runtime_handoff(self, requested_path: str, *, runtime: str = "onyx") -> None:
        """Serve runtime handoff with governance enforcement.
        
        Before allowing handoff to a runtime, check governance policies.
        Block handoff if policy/retrieval/tools deny the access.
        Emit decision events for audit trail.
        """
        safe_path = requested_path if requested_path.startswith("/") else f"/{requested_path.lstrip('/')}"
        safe_path_html = escape(safe_path)
        flow_result = None
        error_reason = None
        target = _runtime_target(runtime or "onyx")
        runtime_name = target.key
        runtime_title = target.label
        parsed = urlparse(getattr(self, "path", f"/launch/{runtime_name}?path={quote(safe_path, safe='/?=&')}"))
        query = parse_qs(parsed.query)
        flow_mode = _governance_mode(query.get("mode", [""])[-1] if query.get("mode") else "")
        view_mode = query.get("view", [""])[-1].strip().lower()
        dashboard_workspace_view = view_mode in {"dashboard", "embedded", "workspace"}
        live_mode = flow_mode == "live"
        question = query.get("question", [f"Navigate to {runtime_title} path: {safe_path}"])[-1]

        def launch_view_href(path: str, *, mode: str = "", view: str = "") -> str:
            href = f"/launch/{runtime_name}?path={quote(path, safe='/?=&')}"
            if mode:
                href = f"{href}&mode={quote(mode, safe='')}"
            if view:
                href = f"{href}&view={quote(view, safe='')}"
            return href

        default_tenant_id = _default_tenant_id()

        # Run governance check for runtime handoff
        try:
            policy_context = _runtime_policy_context()
            runtime_controls = _runtime_controls(policy_context.document, runtime_name)
            surface_info = _resolve_surface(policy_context.document, safe_path)
            evaluator = _build_governed_flow_evaluator(policy_context, flow_mode=flow_mode)
            retrieval_needed_for_runtime = live_mode and bool(runtime_controls.get("require_retrieval_security", target.runtime_class == "rag"))
            requested_mcp_server = query.get("mcp", ["mcp_server.dashboard_control_plane"])[-1]
            requested_action = query.get("action", [""])[-1].strip().lower()
            requested_tools = [target.tool_name]
            if runtime_name == "dify":
                approval_required_actions = set(runtime_controls.get("approval_required_actions", []))
                approval_required_tools = list(runtime_controls.get("approval_required_tools", []))
                if requested_action and requested_action in approval_required_actions:
                    requested_tools.extend(approval_required_tools)

            flow_result = evaluator.run(
                user_id=_dashboard_user_id(),
                tenant_id=default_tenant_id,
                prompt=question,
                requested_tools=requested_tools,
                retrieval_source="qdrant",
                retrieval_needed=retrieval_needed_for_runtime,
                roles=["tenant_user"],
                request_metadata={
                    "requested_path": safe_path,
                    "runtime_key": runtime_name,
                    "runtime_class": target.runtime_class,
                    "requested_mcp_server": requested_mcp_server if runtime_name == "dify" else "",
                    "surface": surface_info.get("surface", ""),
                    "surface_query": surface_info.get("query", {}),
                },
                tool_arguments={
                    target.tool_name: {
                        "surface": surface_info.get("surface", ""),
                        "path": surface_info.get("path", safe_path),
                        "chat_mode": surface_info.get("query", {}).get("chatMode", ""),
                        **({"mcp_server": requested_mcp_server} if runtime_name == "dify" else {}),
                        **({"action": requested_action} if runtime_name == "dify" and requested_action else {}),
                    }
                }
                | (
                    {
                        tool: {
                            "action": requested_action,
                            "runtime": runtime_name,
                        }
                        for tool in requested_tools
                        if tool != target.tool_name
                    }
                ),
                policy_source=policy_context.source,
                policy_path=policy_context.relative_path,
                authorization_header=self.headers.get("Authorization", ""),
                cookies=_cookie_map(self.headers.get("Cookie", "")),
                evidence_mode=flow_mode,
                secret_request={
                    "needed": live_mode,
                    "secret_path": _runtime_secret_path(target, default_tenant_id),
                    "secret_key": os.environ.get("CONTROL_PLANE_RUNTIME_SECRET_KEY", "api_token"),
                    "purpose": f"{runtime_name}_runtime_handoff",
                }
                if live_mode
                else None,
            )
        except Exception as e:
            error_reason = f"{type(e).__name__}: {e}"

        # Determine if handoff is allowed
        governance_allowed = flow_result.decision if flow_result else False
        runtime_port = _runtime_port(target)
        local_url = f"http://127.0.0.1:{runtime_port}{safe_path}"
        public_url = _public_service_url(runtime_port, safe_path)

        if not governance_allowed:
            runtime_proof = _record_runtime_proof(
                target=target,
                requested_path=safe_path,
                governance_allowed=False,
                flow_result=flow_result,
                flow_mode=flow_mode,
                local_ready=None,
                public_ready=None,
                local_url=local_url,
                public_url=public_url,
            )
            if flow_result:
                flow_result.artifacts[f"{runtime_name}_runtime_proof"] = str(runtime_proof.get("artifact", ""))
            denial_reasons = [escape(reason) for reason in (flow_result.reasons if flow_result else [f"Evaluator error: {error_reason or 'governance check failed'}"])]
            artifact_markup = _artifact_list_markup(flow_result.artifacts if flow_result else {})
            dependency_markup = _dependency_summary_markup(flow_result)
            runtime_proof_section = _runtime_proof_markup(runtime_proof)
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
      <p>Present a valid Keycloak-backed bearer token or enter through the deployment's OIDC front door before retrying the live workspace.</p>
      <p><a href="/">Return to dashboard</a></p>
      <div class="status">
        <strong>Handoff to {runtime_title} was denied by control-plane policy.</strong>
        <div class="muted">Evidence mode: <code>{escape(flow_result.evidence_mode if flow_result else flow_mode)}</code></div>
        <div class="muted">Governance decision: {flow_result.launch_gate_decision if flow_result else 'error'}</div>
        <div class="muted">Trace ID: <code>{flow_result.trace_id if flow_result else 'unknown'}</code></div>
        <div class="muted">Session ID: <code>{flow_result.session_id if flow_result and flow_result.session_id else 'missing'}</code></div>
        <div class="muted">Policy source: <code>{escape(flow_result.policy_source if flow_result else 'unknown')}</code> via <code>{escape(flow_result.policy_path if flow_result else 'unknown')}</code></div>
        <div class="muted">Missing evidence: <code>{escape(', '.join(flow_result.launch_gate_missing_evidence) if flow_result and flow_result.launch_gate_missing_evidence else 'none')}</code></div>
      </div>
      <p><strong>Reasons for denial:</strong></p>
      <ul>
        {"".join(f"<li>{reason}</li>" for reason in denial_reasons)}
      </ul>
      {runtime_proof_section}
      <p><strong>Dependency status:</strong></p>
      <ul>
        {dependency_markup}
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
        local_ready = self._url_is_reachable(local_url)
        codespaces_visible = self._url_is_reachable(_public_service_url(runtime_port))
        runtime_proof = _record_runtime_proof(
            target=target,
            requested_path=safe_path,
            governance_allowed=True,
            flow_result=flow_result,
            flow_mode=flow_mode,
            local_ready=local_ready,
            public_ready=codespaces_visible,
            local_url=local_url,
            public_url=public_url,
        )
        if flow_result:
            flow_result.artifacts[f"{runtime_name}_runtime_proof"] = str(runtime_proof.get("artifact", ""))
        runtime_proof_section = _runtime_proof_markup(runtime_proof)

        if local_ready and codespaces_visible:
            runtime_summary = (
                f"The control plane found a reachable {runtime_title} runtime on local port <code>{runtime_port}</code> "
                f"and prepared the link for <code>{safe_path_html}</code>."
            )
            status_headline = f"Local {runtime_title} is running."
            status_detail = "The public Codespaces URL appears reachable."
            next_steps = """
      <p>The governed runtime looks reachable from both the local service and the public Codespaces URL.</p>
"""
        elif local_ready and not codespaces_visible:
            runtime_summary = (
                f"The control plane found a reachable {runtime_title} runtime on local port <code>{runtime_port}</code> "
                f"and prepared the link for <code>{safe_path_html}</code>."
            )
            status_headline = f"Local {runtime_title} is running."
            status_detail = f"The public Codespaces port for {runtime_port} is still protected by the tunnel."
            next_steps = f"""
      <p>If this still opens a <code>401 tunnel</code> page, expose port <code>{runtime_port}</code> in the Codespaces <strong>Ports</strong> tab and then try again.</p>
      <ol>
        <li>Open the <strong>Ports</strong> tab in Codespaces.</li>
        <li>Find port <code>{runtime_port}</code>.</li>
        <li>Use <strong>Open in Browser</strong> or change visibility from <code>Private</code> to <code>Public</code> or <code>Organization</code>.</li>
      </ol>
"""
        elif not local_ready and codespaces_visible:
            runtime_summary = (
                f"Governance approved the handoff, but the configured {runtime_title} runtime on local port <code>{runtime_port}</code> "
                f"is not responding for <code>{safe_path_html}</code>."
            )
            status_headline = f"Local {runtime_title} is not responding yet."
            status_detail = f"The public Codespaces URL is reachable, so the remaining issue is the local {runtime_title} service itself."
            next_steps = f"""
      <p>Port exposure is not the blocker here. Start or repair the local {runtime_title} runtime bound to port <code>{runtime_port}</code>, then retry the governed handoff.</p>
"""
        else:
            runtime_summary = (
                f"Governance approved the handoff, but the configured {runtime_title} runtime on local port <code>{runtime_port}</code> "
                f"is not responding for <code>{safe_path_html}</code>."
            )
            status_headline = f"Local {runtime_title} is not responding yet."
            status_detail = f"The public Codespaces port is also not reachable, but exposing the port alone will not fix this until the {runtime_title} service is running."
            next_steps = f"""
      <p>Start the local {runtime_title} runtime on port <code>{runtime_port}</code> first. After that, if the public URL still shows a tunnel page, expose port <code>{runtime_port}</code> in the Codespaces <strong>Ports</strong> tab.</p>
      <ol>
        <li>Start or repair the {runtime_title} runtime bound to port <code>{runtime_port}</code>.</li>
        <li>Open the <strong>Ports</strong> tab in Codespaces.</li>
        <li>Find port <code>{runtime_port}</code>.</li>
        <li>Use <strong>Open in Browser</strong> or change visibility from <code>Private</code> to <code>Public</code> or <code>Organization</code>.</li>
      </ol>
"""

        if dashboard_workspace_view:
            workspace_poll_ms = 5000
            if target.key == "onyx":
                workspace_activity = build_onyx_workspace_activity(
                    REPO_ROOT,
                    requested_path=safe_path,
                    trace_id=str(flow_result.trace_id if flow_result else ""),
                    session_id=str(flow_result.session_id if flow_result and flow_result.session_id else ""),
                    limit=4,
                )
                activity_api_href = f"{str(workspace_activity.get('source_href', ''))}&format=html"
                workspace_poll_ms = int(workspace_activity.get("poll_interval_ms", 5000))
                workspace_activity_markup = _workspace_activity_panel_markup(workspace_activity)
            else:
                activity_api_href = ""
                workspace_activity_markup = (
                    f"<section class='activity-panel-shell'><div class='activity-panel-head'><div><p class='eyebrow'>Current {escape(runtime_title)} activity</p><h2>Current {escape(runtime_title)} Activity</h2><p class='activity-panel-summary'>Runtime-specific activity feed is not yet instrumented in this view.</p></div><div class='activity-panel-summary-badge activity-panel-summary-neutral'>Preview</div></div></section>"
                )
            workspace_nav = [
                ("Chat", launch_view_href("/app", mode="live", view="embedded")) if runtime_name == "onyx" else ("Apps", launch_view_href("/apps", mode="live", view="embedded")),
                ("Search", launch_view_href("/app?chatMode=search", mode="live", view="embedded")) if runtime_name == "onyx" else ("Workflows", launch_view_href("/apps/workflows", mode="live", view="embedded")),
                ("Agents", launch_view_href("/app/agents", mode="live", view="embedded")) if runtime_name == "onyx" else ("Tools", launch_view_href("/apps/tools", mode="live", view="embedded")),
            ]
            workspace_nav_markup = "".join(
                f'<a class="surface-link{" is-active" if href == launch_view_href(safe_path, mode="live", view="embedded") else ""}" href="{href}">{label}</a>'
                for label, href in workspace_nav
            )
            workspace_main_markup = ""
            frame_callout_markup = ""
            if codespaces_visible:
                frame_callout_markup = (
                    f'<p class="frame-status">The live runtime target responded to the public dashboard handoff, so you can use {runtime_title} here without leaving the control-plane shell.</p>'
                )
                workspace_main_markup = f"""
      <section class="workspace-runtime" aria-label="Live {runtime_title} runtime">
        <iframe
          class="runtime-frame"
          src="{public_url}"
          title="Live {runtime_title} runtime for {safe_path_html}"
          loading="eager"
          referrerpolicy="no-referrer"
        ></iframe>
      </section>
"""
            else:
                frame_callout_markup = f"""
        <div class="status-note">The live handoff passed, but the browser still cannot reach the public {runtime_title} port yet. Use the checklist below to bring the runtime online and then re-check governance.</div>
"""
                workspace_main_markup = f"""
      <div class="runtime-placeholder">
        <h2>Runtime frame is not reachable yet</h2>
        <p>The dashboard approved this live handoff, but the public {runtime_title} port is not reachable from the browser yet for <code>{safe_path_html}</code>.</p>
        <ol class="runtime-fallback-list">
          <li>Start or repair the local {runtime_title} service.</li>
          <li>Expose port <code>{runtime_port}</code> in the Codespaces <strong>Ports</strong> tab if the public URL is still hidden behind the tunnel.</li>
          <li>Use <strong>Re-check governance</strong> after the runtime responds so the embedded frame can load inside this workspace.</li>
        </ol>
        <div class="runtime-fallback-actions">
          <a class="runtime-fallback-link" href="{public_url}" target="_blank" rel="noreferrer">Open public runtime target</a>
          <a class="runtime-fallback-link" href="{launch_view_href(safe_path, mode='live', view='embedded')}">Retry workspace check</a>
        </div>
      </div>
"""
            runtime_health_note_markup = ""
            if codespaces_visible and not local_ready:
                runtime_health_note_markup = (
                    '<div class="status-note">Local runtime health is still degraded. The dashboard is showing the live surface only because the public target responded.</div>'
                )

            body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Live Runtime Workspace</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4efe6;
        --panel: #fffdf8;
        --panel-alt: #f8f2e8;
        --ink: #1f2430;
        --muted: #576072;
        --border: #d8cfc2;
        --accent: #a03d26;
        --accent-soft: #f5e1da;
        --healthy: #1f6f43;
        --warning: #8a5a12;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top left, #fff8eb 0%, rgba(255, 248, 235, 0.2) 35%, transparent 60%),
          linear-gradient(180deg, #efe6d9 0%, var(--bg) 58%, #ede7df 100%);
        color: var(--ink);
      }}
      .workspace-shell {{
        min-height: 100vh;
        padding: 28px;
        display: grid;
        grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
        gap: 22px;
      }}
      .workspace-panel,
      .workspace-runtime,
      .runtime-placeholder {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 24px;
        box-shadow: 0 18px 60px rgba(31, 36, 48, 0.12);
      }}
      .workspace-panel {{
        padding: 24px;
      }}
      .workspace-runtime,
      .runtime-placeholder {{
        min-height: calc(100vh - 56px);
        overflow: hidden;
      }}
      .runtime-placeholder {{
        padding: 28px;
        display: grid;
        align-content: start;
        gap: 12px;
      }}
      .eyebrow {{
        margin: 0 0 10px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        font-size: 0.72rem;
        color: var(--muted);
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2rem, 3vw, 2.8rem);
      }}
      p {{
        line-height: 1.6;
      }}
      .lede {{
        color: var(--muted);
        margin: 14px 0 20px;
      }}
      .toolbar,
      .surface-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .toolbar {{
        margin: 18px 0 22px;
      }}
      .toolbar a,
      .surface-link {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 42px;
        padding: 0 16px;
        border-radius: 999px;
        text-decoration: none;
        border: 1px solid var(--border);
        color: var(--ink);
        background: #fffaf2;
        font-weight: 600;
      }}
      .toolbar a.primary {{
        background: var(--accent);
        color: white;
        border-color: var(--accent);
      }}
      .surface-link.is-active {{
        background: var(--accent-soft);
        border-color: #cf8d76;
      }}
      .signal-grid {{
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        margin: 18px 0 22px;
      }}
      .signal-card {{
        background: var(--panel-alt);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 14px 16px;
      }}
      .signal-card strong,
      .signal-card code {{
        display: block;
        margin-top: 6px;
      }}
      .activity-panel {{
        margin: 18px 0 0;
      }}
      .activity-panel-shell {{
        padding: 18px;
        border: 1px solid var(--border);
        border-radius: 22px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(248, 242, 232, 0.86));
      }}
      .activity-panel-head,
      .activity-group-head,
      .activity-panel-footer,
      .activity-entry-head,
      .activity-entry-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: space-between;
        align-items: flex-start;
      }}
      .activity-panel-head {{
        margin-bottom: 14px;
      }}
      .activity-panel-head h2,
      .activity-group-head h3 {{
        margin: 0;
      }}
      .activity-panel-summary,
      .activity-group-head p,
      .activity-entry-detail,
      .activity-group-empty,
      .activity-panel-error {{
        margin: 8px 0 0;
        color: var(--muted);
      }}
      .activity-panel-summary-badge,
      .activity-panel-chip,
      .activity-entry-chip,
      .activity-group-count {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 34px;
        padding: 0 12px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: #fffaf2;
        font-size: 0.84rem;
        font-weight: 600;
      }}
      .activity-panel-summary-healthy {{
        color: var(--healthy);
        background: #eef6f0;
        border-color: #b8d0bf;
      }}
      .activity-panel-summary-warning {{
        color: var(--warning);
        background: #fff4e5;
        border-color: #e2c48e;
      }}
      .activity-panel-summary-critical {{
        color: #a03d26;
        background: #fbe8e2;
        border-color: #e0b4a4;
      }}
      .activity-panel-chips,
      .activity-panel-groups {{
        display: grid;
        gap: 12px;
      }}
      .activity-panel-chips {{
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin-bottom: 14px;
      }}
      .activity-group {{
        padding: 14px 16px;
        border: 1px solid var(--border);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.74);
      }}
      .activity-group-empty {{
        padding: 8px 0 0;
      }}
      .activity-entry {{
        margin-top: 12px;
        padding: 14px;
        border: 1px solid rgba(31, 36, 48, 0.08);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.84);
      }}
      .activity-entry-current_surface {{
        box-shadow: inset 0 0 0 1px rgba(31, 111, 67, 0.08);
      }}
      .activity-entry-correlated {{
        box-shadow: inset 0 0 0 1px rgba(138, 90, 18, 0.08);
      }}
      .activity-entry-time {{
        color: var(--muted);
        font-size: 0.82rem;
      }}
      .activity-entry-detail {{
        line-height: 1.5;
      }}
      .activity-entry-meta {{
        margin-top: 10px;
        justify-content: flex-start;
      }}
      .activity-entry-chip-match {{
        color: var(--healthy);
        background: #eef6f0;
        border-color: #b8d0bf;
      }}
      .activity-panel-footer {{
        margin-top: 14px;
        padding-top: 14px;
        border-top: 1px solid var(--border);
        align-items: end;
      }}
      .activity-panel-limitations {{
        margin: 8px 0 0;
        padding-left: 18px;
      }}
      .activity-panel-limitations li {{
        margin: 0 0 8px;
      }}
      .activity-panel-link {{
        display: inline-flex;
        align-items: center;
        min-height: 42px;
        padding: 0 16px;
        border-radius: 999px;
        text-decoration: none;
        border: 1px solid var(--border);
        color: var(--ink);
        background: #fffaf2;
        font-weight: 600;
      }}
      .checklist {{
        margin: 0;
        padding-left: 18px;
      }}
      .checklist li {{
        margin: 0 0 8px;
      }}
      .frame-status {{
        margin: 18px 0 0;
        padding: 14px 16px;
        border-radius: 18px;
        background: #eef6f0;
        border: 1px solid #b8d0bf;
        color: var(--healthy);
      }}
      .runtime-frame {{
        width: 100%;
        height: calc(100vh - 56px);
        border: 0;
        background: white;
      }}
      .status-note {{
        margin: 18px 0 0;
        padding: 14px 16px;
        border-radius: 18px;
        background: #fff4e5;
        border: 1px solid #e2c48e;
        color: var(--warning);
      }}
      .runtime-fallback-list {{
        margin: 4px 0 0;
        padding-left: 18px;
      }}
      .runtime-fallback-list li {{
        margin: 0 0 10px;
      }}
      .runtime-fallback-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 8px;
      }}
      .runtime-fallback-link {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 42px;
        padding: 0 16px;
        border-radius: 999px;
        text-decoration: none;
        border: 1px solid var(--border);
        color: var(--ink);
        background: #fffaf2;
        font-weight: 600;
      }}
      .proof-block {{
        margin-top: 22px;
        padding-top: 20px;
        border-top: 1px solid var(--border);
      }}
      code {{
        font-family: "SFMono-Regular", Consolas, monospace;
        background: #f3eee6;
        padding: 2px 6px;
        border-radius: 6px;
      }}
      @media (max-width: 1100px) {{
        .workspace-shell {{
          grid-template-columns: 1fr;
        }}
        .workspace-runtime,
        .runtime-placeholder {{
          min-height: 70vh;
        }}
        .runtime-frame {{
          height: 70vh;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="workspace-shell">
      <section class="workspace-panel">
        <p class="eyebrow">Dashboard-owned live runtime</p>
        <h1>Live Runtime Workspace</h1>
        <p class="lede">
          Governance approved the live handoff for <code>{safe_path_html}</code>. This page keeps the control-plane context, traceability, and runtime access together in one dashboard-owned workspace.
        </p>
        <div class="toolbar">
          <a class="primary" href="{public_url}" target="_blank" rel="noreferrer">Open in new tab</a>
          <a href="/">Return to dashboard</a>
          <a href="{launch_view_href(safe_path, mode='live', view='embedded')}">Re-check governance</a>
        </div>
        <div class="surface-links" aria-label="Switch live Onyx surface">
          {workspace_nav_markup}
        </div>
        <div class="signal-grid">
          <div class="signal-card">
            Requested path
            <code>{safe_path_html}</code>
          </div>
          <div class="signal-card">
            Evidence mode
            <strong>{escape(flow_result.evidence_mode if flow_result else flow_mode)}</strong>
          </div>
          <div class="signal-card">
            Trace ID
            <code>{flow_result.trace_id if flow_result else 'unknown'}</code>
          </div>
          <div class="signal-card">
            Session ID
            <code>{flow_result.session_id if flow_result and flow_result.session_id else 'missing'}</code>
          </div>
        </div>
        <div
          class="activity-panel"
          id="workspace-activity-root"
          data-activity-url="{escape(activity_api_href, quote=True)}"
          data-poll-ms="{escape(str(workspace_poll_ms), quote=True)}"
        >
          {workspace_activity_markup}
        </div>
        {frame_callout_markup}
        {runtime_health_note_markup}
        <div class="proof-block">
          <p class="eyebrow">Why access was allowed</p>
          <ul class="checklist">
            <li>Identity, policy, retrieval, secret access, trace, and launch-gate checks were evaluated under the same governed flow.</li>
            <li>Runtime proof was written at <code>{escape(str(runtime_proof.get("artifact", "")))}</code>.</li>
            <li>Missing evidence: <code>{escape(', '.join(flow_result.launch_gate_missing_evidence) if flow_result and flow_result.launch_gate_missing_evidence else 'none')}</code></li>
            <li>This workspace uses a dev-only session bootstrap for local testing. Every refresh still re-runs governance before the runtime frame is shown.</li>
          </ul>
        </div>
        <div class="proof-block">
          <strong>Governance audit trail</strong>
          <p>Policy source: <code>{escape(flow_result.policy_source if flow_result else 'unknown')}</code> via <code>{escape(flow_result.policy_path if flow_result else 'unknown')}</code></p>
          <p>Reasons: <code>{escape(', '.join(flow_result.reasons) if flow_result and flow_result.reasons else 'policy.allow')}</code></p>
          {runtime_proof_section}
        </div>
      </section>
      {workspace_main_markup}
    </main>
    <script>
      (() => {{
        const activityRoot = document.getElementById("workspace-activity-root");
        if (!activityRoot) {{
          return;
        }}

        const activityUrl = activityRoot.dataset.activityUrl || "";
        const pollMs = Number(activityRoot.dataset.pollMs || "5000") || 5000;
        if (!activityUrl) {{
          return;
        }}

        let timer = 0;
        const schedule = () => {{
          window.clearTimeout(timer);
          timer = window.setTimeout(refreshActivity, pollMs);
        }};

        async function refreshActivity() {{
          try {{
            const response = await fetch(activityUrl, {{ cache: "no-store" }});
            if (!response.ok) {{
              throw new Error(`${runtime_title} activity API returned ${{response.status}}`);
            }}
            activityRoot.innerHTML = await response.text();
          }} catch (error) {{
            activityRoot.innerHTML = `
              <section class="activity-panel-shell">
                <div class="activity-panel-head">
                  <div>
                    <p class="eyebrow">Current {runtime_title} activity</p>
                    <h2>Current {runtime_title} Activity</h2>
                    <p class="activity-panel-error">${{String(error.message || "Unknown error")}}</p>
                  </div>
                  <div class="activity-panel-summary-badge activity-panel-summary-warning">Refresh issue</div>
                </div>
              </section>
            `;
          }} finally {{
            schedule();
          }}
        }}

        schedule();
      }})();
    </script>
  </body>
</html>
"""
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        body = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Open {runtime_title}</title>
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
      <h1>{runtime_title} Launch Handoff</h1>
      <p>{runtime_summary}</p>
      <p><strong>Governance Status:</strong> ✓ Approved by control-plane policy.</p>
      <div class="status">
        <strong>{status_headline}</strong>
        <div class="muted">{status_detail}</div>
        <div class="muted">Evidence mode: <code>{escape(flow_result.evidence_mode if flow_result else flow_mode)}</code></div>
        <div class="muted">Session ID: <code>{flow_result.session_id if flow_result and flow_result.session_id else 'missing'}</code></div>
        <div class="muted">Missing evidence: <code>{escape(', '.join(flow_result.launch_gate_missing_evidence) if flow_result and flow_result.launch_gate_missing_evidence else 'none')}</code></div>
      </div>
      <div class="actions">
        <a class="button" href="{public_url}">Open {runtime_title}</a>
      </div>
      <p class="muted">Target URL: <code>{public_url}</code></p>
      {next_steps}
      {runtime_proof_section}
      <div class="governance">
        <strong>Governance Audit Trail:</strong><br>
        Trace: <code>{flow_result.trace_id if flow_result else 'unknown'}</code><br>
        Decision: <code>{flow_result.launch_gate_decision if flow_result else 'pass'}</code><br>
        Policy Source: <code>{escape(flow_result.policy_source if flow_result else 'unknown')}</code> via <code>{escape(flow_result.policy_path if flow_result else 'unknown')}</code><br>
        Identity: {"Live" if flow_result and flow_result.dependency_status.get('identity', {}).get('live') else "Fallback"} |
        Policy: {"Allow" if flow_result and flow_result.policy_allow else "Deny"} |
        Retrieval: {"Allow" if flow_result and flow_result.retrieval_allow else "Deny"} |
        Secret: {"Allow" if flow_result and (not flow_result.dependency_status.get('secret', {}).get('mandatory') or flow_result.dependency_status.get('secret', {}).get('fetched')) else "Deny"} |
        Trace: {"Complete" if flow_result and flow_result.dependency_status.get('trace', {}).get('complete') else "Incomplete"} |
        Tools: {"Allow" if flow_result and not flow_result.denied_tools else "Deny"}<br>
        Reasons: <code>{escape(", ".join(flow_result.reasons) if flow_result and flow_result.reasons else "policy.allow")}</code><br>
        <strong>Dependency status:</strong>
        <ul>
          {_dependency_summary_markup(flow_result)}
        </ul>
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
    _validate_startup_configuration()
    host = os.environ.get("CONTROL_PLANE_HOST", "0.0.0.0")
    port = int(os.environ.get("CONTROL_PLANE_PORT", "3000"))
    server = ThreadingHTTPServer((host, port), ControlPlaneRequestHandler)
    print(f"Control plane listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
