from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.integration_adapter.repository import (
    ONYX_RUNTIME_PROOF_PATH,
    repo_root,
    read_json,
)
from backend.trust_readiness.evidence import evidence_age_status, latest_timestamp, load_evidence_bundle
from backend.trust_readiness.readiness import compute_runtime_readiness

from ..enums import FailureCategory, FreshnessStatus, RuntimeLane, Severity
from ..models import DiagnosticFinding, DiagnosticReport, iso_now, new_id

Probe = Callable[[str], bool]


@dataclass(frozen=True)
class RuntimeRouteConfig:
    lane: RuntimeLane
    runtime_id: str
    label: str
    default_path: str
    local_base_url: str
    public_base_url: str
    expected_routes: list[str]
    proof_path: str


@dataclass
class DiagnosticContext:
    tenant_id: str
    actor_id: str
    correlation_id: str
    decision_id: str = field(default_factory=lambda: new_id("repair-decision"))
    root: Path | None = None
    prober: Probe | None = None
    environment: str = "dev"


def default_url_probe(url: str) -> bool:
    try:
        request = Request(url, method="GET")
        request.add_header("User-Agent", "governed-runtime-repair/1.0")
        with urlopen(request, timeout=5) as response:
            return 200 <= int(getattr(response, "status", 0)) < 400
    except HTTPError as exc:
        return 200 <= exc.code < 400
    except (URLError, TimeoutError, ValueError):
        return False


def _join_url(base: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base.rstrip('/')}{normalized_path}"


class RuntimeDiagnosticAdapter:
    lane = RuntimeLane.ONYX

    def __init__(self, config: RuntimeRouteConfig) -> None:
        self.config = config

    def diagnose(self, context: DiagnosticContext) -> DiagnosticReport:
        root = repo_root(context.root)
        bundle = load_evidence_bundle(root)
        readiness = compute_runtime_readiness(root, runtime_id=self.config.runtime_id)
        runtime_proof = read_json(root / self.config.proof_path)
        evidence_refs = bundle.evidence_refs()
        evidence_refs["runtime_proof"] = self.config.proof_path

        findings: list[DiagnosticFinding] = []
        findings.extend(self._target_findings(context))
        findings.extend(self._route_findings(context))
        findings.extend(self._handoff_findings(context, runtime_proof))
        findings.extend(self._dependency_findings(context, bundle))
        findings.extend(self._freshness_findings(context, bundle, runtime_proof))
        findings.extend(self._launch_gate_findings(context, bundle, readiness.to_dict(), runtime_proof))
        findings.extend(self._lane_specific_findings(context, bundle, readiness.to_dict(), runtime_proof))

        if not findings:
            findings.append(
                self._finding(
                    context,
                    Severity.INFO,
                    FailureCategory.UNKNOWN,
                    "No active repair findings",
                    f"{self.config.label} has no diagnostic findings from current evidence.",
                    evidence_used=list(evidence_refs.values()),
                    reason_codes=["repair.no_findings"],
                )
            )

        highest = self._highest_severity(findings)
        summary = f"{self.config.label} repair diagnostics found {len(findings)} issue(s); highest severity is {highest.value}."
        return DiagnosticReport(
            report_id=new_id("diagnostic-report"),
            lane=self.config.lane,
            tenant_id=context.tenant_id,
            runtime_id=self.config.runtime_id,
            correlation_id=context.correlation_id,
            actor_id=context.actor_id,
            generated_at=iso_now(),
            findings=findings,
            evidence_refs=evidence_refs,
            readiness_before=readiness.to_dict(),
            summary=summary,
        )

    def _probe(self, context: DiagnosticContext, url: str) -> bool:
        return (context.prober or default_url_probe)(url)

    def _target_findings(self, context: DiagnosticContext) -> list[DiagnosticFinding]:
        findings: list[DiagnosticFinding] = []
        if not self.config.local_base_url:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.CONFIG_DRIFT,
                    "Runtime local target is not configured",
                    f"{self.config.label} has no local runtime base URL configured.",
                    reason_codes=["config.target_missing.local"],
                )
            )
        if not self.config.public_base_url:
            findings.append(
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.CONFIG_DRIFT,
                    "Runtime public target is not configured",
                    f"{self.config.label} has no public runtime base URL configured for browser handoff.",
                    reason_codes=["config.target_missing.public"],
                )
            )
        return findings

    def _route_findings(self, context: DiagnosticContext) -> list[DiagnosticFinding]:
        if not self.config.local_base_url:
            return []
        local_results = {route: self._probe(context, _join_url(self.config.local_base_url, route)) for route in self.config.expected_routes}
        public_results = {route: self._probe(context, _join_url(self.config.public_base_url, route)) for route in self.config.expected_routes} if self.config.public_base_url else {}
        local_any = any(local_results.values())
        public_any = any(public_results.values())
        findings: list[DiagnosticFinding] = []
        if local_any and not public_any:
            findings.append(
                self._finding(
                    context,
                    Severity.WARNING,
                    FailureCategory.REACHABILITY,
                    "Runtime is locally reachable but public handoff is unreachable",
                    f"{self.config.label} responds locally, but the public URL did not respond on expected routes.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["reachability.local_ok_public_unreachable"],
                    details={"local_routes": local_results, "public_routes": public_results},
                )
            )
        elif not local_any and public_any:
            findings.append(
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.REACHABILITY,
                    "Public URL responds but local runtime target is unhealthy",
                    f"{self.config.label} public route responded while the configured local runtime route did not.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["reachability.public_ok_local_unhealthy"],
                    details={"local_routes": local_results, "public_routes": public_results},
                )
            )
        elif not local_any and not public_any:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.REACHABILITY,
                    "Runtime routes are unreachable",
                    f"{self.config.label} did not respond on local or public expected routes.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["reachability.routes_unreachable"],
                    details={"local_routes": local_results, "public_routes": public_results},
                )
            )
        return findings

    def _handoff_findings(self, context: DiagnosticContext, runtime_proof: dict[str, Any]) -> list[DiagnosticFinding]:
        handoff_allowed = bool(runtime_proof.get("handoff_allowed", False))
        continuity = runtime_proof.get("continuity", {}) if isinstance(runtime_proof.get("continuity"), dict) else {}
        continuity_status = str(continuity.get("status", ""))
        if not runtime_proof:
            return [
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.CONTINUITY,
                    "Runtime proof is missing",
                    f"{self.config.label} has no post-handoff runtime proof artifact.",
                    evidence_used=[self.config.proof_path],
                    freshness=FreshnessStatus.MISSING,
                    reason_codes=["runtime_proof.missing"],
                )
            ]
        if not handoff_allowed:
            return [
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.LAUNCH_GATE,
                    "Governed handoff is failing",
                    f"{self.config.label} runtime proof shows the governed handoff was not allowed.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["handoff.denied"],
                    details={"launch_gate_decision": runtime_proof.get("launch_gate_decision", "")},
                )
            ]
        if continuity_status in {"", "no_runtime_activity", "blocked_before_runtime"}:
            return [
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.CONTINUITY,
                    "Governed handoff allowed but continuity proof is missing",
                    f"{self.config.label} was allowed by governance, but post-handoff continuity proof is absent.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["continuity.missing_after_allowed_handoff"],
                    details={"continuity": continuity},
                )
            ]
        return []

    def _dependency_findings(self, context: DiagnosticContext, bundle: Any) -> list[DiagnosticFinding]:
        checks = [
            ("identity", bundle.identity, "authenticated", FailureCategory.IDENTITY, "identity.unhealthy"),
            ("policy", bundle.policy, "allow", FailureCategory.POLICY, "policy.unhealthy"),
            ("secret", bundle.secret, "fetched", FailureCategory.SECRETS, "secret.unhealthy"),
        ]
        findings: list[DiagnosticFinding] = []
        for label, document, ok_key, category, reason in checks:
            required = bool(document.get("required", True)) if label == "secret" else True
            if required and not bool(document.get(ok_key, False)):
                findings.append(
                    self._finding(
                        context,
                        Severity.CRITICAL if label in {"identity", "policy"} else Severity.HIGH,
                        category,
                        f"{label.title()} dependency is unhealthy",
                        f"{self.config.label} cannot be repaired into readiness while {label} evidence is unhealthy.",
                        evidence_used=[bundle.evidence_refs().get(label, "")],
                        reason_codes=list(document.get("reason_codes", []) or [reason]),
                        details=document,
                    )
                )
        return findings

    def _freshness_findings(self, context: DiagnosticContext, bundle: Any, runtime_proof: dict[str, Any]) -> list[DiagnosticFinding]:
        findings: list[DiagnosticFinding] = []
        docs = {
            "identity": bundle.identity,
            "policy": bundle.policy,
            "retrieval": bundle.retrieval,
            "secret": bundle.secret,
            "tool": bundle.tool,
            "trace": bundle.trace,
            "runtime_proof": runtime_proof,
        }
        refs = {**bundle.evidence_refs(), "runtime_proof": self.config.proof_path}
        for label, document in docs.items():
            if not document:
                findings.append(
                    self._finding(
                        context,
                        Severity.HIGH if label in {"identity", "policy", "trace", "runtime_proof"} else Severity.WARNING,
                        FailureCategory.EVIDENCE_FRESHNESS,
                        f"{label.replace('_', ' ').title()} evidence is missing",
                        f"{self.config.label} has no current {label} evidence.",
                        evidence_used=[refs.get(label, "")],
                        freshness=FreshnessStatus.MISSING,
                        reason_codes=[f"evidence.missing:{label}"],
                    )
                )
                continue
            timestamp = latest_timestamp(document)
            age = evidence_age_status(timestamp)
            if age in {"stale", "missing"}:
                findings.append(
                    self._finding(
                        context,
                        Severity.HIGH,
                        FailureCategory.EVIDENCE_FRESHNESS,
                        f"{label.replace('_', ' ').title()} evidence is {age}",
                        f"{self.config.label} has {age} {label} evidence, so launch readiness cannot rely on it.",
                        evidence_used=[refs.get(label, "")],
                        freshness=FreshnessStatus(age),
                        reason_codes=[f"evidence.{age}:{label}"],
                        details={"observed_at": timestamp},
                    )
                )
        evidence_mode = str(runtime_proof.get("evidence_mode") or bundle.summary.get("evidence_mode") or "")
        if evidence_mode == "demo":
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.LAUNCH_GATE,
                    "Demo evidence cannot qualify live readiness",
                    f"{self.config.label} latest proof is demo-only and must not count as live launch proof.",
                    evidence_used=[self.config.proof_path, bundle.evidence_refs().get("summary", "")],
                    reason_codes=["evidence.demo_only_not_live_proof"],
                    details={"evidence_mode": evidence_mode},
                )
            )
        return findings

    def _launch_gate_findings(
        self,
        context: DiagnosticContext,
        bundle: Any,
        readiness: dict[str, Any],
        runtime_proof: dict[str, Any],
    ) -> list[DiagnosticFinding]:
        launch_machine = bundle.launch_gate.get("machine", {}) if isinstance(bundle.launch_gate.get("machine"), dict) else {}
        gate_decision = str(launch_machine.get("decision", ""))
        launch_allowed = bool(readiness.get("launch_allowed", False))
        handoff_allowed = bool(runtime_proof.get("handoff_allowed", False))
        findings: list[DiagnosticFinding] = []
        if gate_decision == "pass" and not launch_allowed:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.LAUNCH_GATE,
                    "Launch gate contradicts computed readiness",
                    f"{self.config.label} launch gate says pass while computed readiness is not launchable.",
                    evidence_used=[bundle.evidence_refs().get("launch_gate", ""), self.config.proof_path],
                    reason_codes=["launch_gate.contradicts_readiness"],
                    details={"gate_decision": gate_decision, "readiness_state": readiness.get("state", "")},
                )
            )
        if gate_decision not in {"pass", "conditional_go"} and handoff_allowed:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.LAUNCH_GATE,
                    "Runtime handoff contradicts launch gate",
                    f"{self.config.label} handoff is marked allowed while the latest launch gate is not GO.",
                    evidence_used=[bundle.evidence_refs().get("launch_gate", ""), self.config.proof_path],
                    reason_codes=["launch_gate.contradicts_handoff"],
                    details={"gate_decision": gate_decision, "handoff_allowed": handoff_allowed},
                )
            )
        return findings

    def _lane_specific_findings(
        self,
        context: DiagnosticContext,
        bundle: Any,
        readiness: dict[str, Any],
        runtime_proof: dict[str, Any],
    ) -> list[DiagnosticFinding]:
        return []

    def _finding(
        self,
        context: DiagnosticContext,
        severity: Severity,
        category: FailureCategory,
        title: str,
        detail: str,
        *,
        evidence_used: list[str] | None = None,
        freshness: FreshnessStatus = FreshnessStatus.FRESH,
        reason_codes: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> DiagnosticFinding:
        safe_categories = {
            FailureCategory.REACHABILITY,
            FailureCategory.EVIDENCE_FRESHNESS,
            FailureCategory.CONFIG_DRIFT,
            FailureCategory.CONTINUITY,
        }
        return DiagnosticFinding(
            finding_id=new_id("finding"),
            lane=self.config.lane,
            tenant_id=context.tenant_id,
            runtime_id=self.config.runtime_id,
            severity=severity,
            category=category,
            title=title,
            detail=detail,
            evidence_used=[ref for ref in (evidence_used or []) if ref],
            correlation_id=context.correlation_id,
            actor_id=context.actor_id,
            decision_id=context.decision_id,
            freshness=freshness,
            safe_to_auto_execute=category in safe_categories and severity != Severity.CRITICAL,
            requires_approval=severity == Severity.CRITICAL,
            policy_basis=["repair.fail_closed", "repair.no_policy_bypass"],
            reason_codes=list(reason_codes or []),
            details=dict(details or {}),
        )

    @staticmethod
    def _highest_severity(findings: list[DiagnosticFinding]) -> Severity:
        rank = {Severity.INFO: 0, Severity.WARNING: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        return max((finding.severity for finding in findings), key=lambda item: rank[item], default=Severity.INFO)


def proof_path_for_lane(lane: RuntimeLane) -> str:
    return ONYX_RUNTIME_PROOF_PATH


def host_from_url(url: str) -> str:
    return urlparse(url).netloc
