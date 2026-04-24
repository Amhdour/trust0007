(function (globalScope) {
  const DEFAULT_ONYX_APP_URL = "https://ubiquitous-spork-r4rrpvw9995wfw7gp-3001.app.github.dev/app";
  const DEFAULT_GOVERNED_ONYX_LAUNCH_PATH = "/launch/onyx?path=/app&mode=live&view=embedded";

  function getConfiguredOnyxAppUrl(payload = {}) {
    const payloadValue = String(payload?.live_onyx_project?.direct_onyx_app_url || "").trim();
    if (payloadValue) {
      return payloadValue;
    }

    const globalConfig = globalScope?.CONTROL_PLANE_DASHBOARD_CONFIG || {};
    const configuredValue = String(
      globalConfig.CONTROL_PLANE_ONYX_APP_URL || globalConfig.CONTROL_PLANE_ONYX_BASE_URL || "",
    ).trim();
    return configuredValue || DEFAULT_ONYX_APP_URL;
  }

  function getGovernedOnyxLaunchPath(payload = {}) {
    const payloadValue = String(payload?.live_onyx_project?.governed_launch_path || "").trim();
    return payloadValue || DEFAULT_GOVERNED_ONYX_LAUNCH_PATH;
  }

  function normalizeEvidenceMode(value) {
    const normalized = String(value || "").trim().toUpperCase();
    if (["LIVE", "PARTIAL", "DEMO", "SAMPLE", "UNKNOWN"].includes(normalized)) {
      return normalized;
    }
    if (!normalized) {
      return "UNKNOWN";
    }
    if (normalized.includes("LIVE")) {
      return "LIVE";
    }
    if (normalized.includes("PARTIAL")) {
      return "PARTIAL";
    }
    if (normalized.includes("SAMPLE")) {
      return "SAMPLE";
    }
    if (normalized.includes("DEMO")) {
      return "DEMO";
    }
    return "UNKNOWN";
  }

  function deriveEvidenceMode(payload = {}) {
    const readinessMode = normalizeEvidenceMode(payload?.readiness?.evidence_mode);
    if (readinessMode !== "UNKNOWN") {
      return readinessMode;
    }

    const modeLabel = String(payload?.data_mode?.label || "");
    const modeDisplay = String(payload?.data_mode?.display_label || "");
    return normalizeEvidenceMode(`${modeLabel} ${modeDisplay}`);
  }

  function deriveOnyxEvidenceMode(payload = {}) {
    return deriveEvidenceMode(payload);
  }

  function mapControlStatus(value, required = true) {
    const normalized = String(value || "").trim().toUpperCase();
    if (["PASS", "FAIL", "WARN", "UNKNOWN", "N/A"].includes(normalized)) {
      return normalized;
    }
    if (["MISSING_PROOF"].includes(normalized)) {
      return required ? "FAIL" : "WARN";
    }
    if (["STALE", "DEMO_ONLY", "NEEDS_ATTENTION"].includes(normalized)) {
      return "WARN";
    }
    if (!normalized) {
      return "UNKNOWN";
    }
    return required ? "FAIL" : "WARN";
  }

  function controlLookup(payload = {}) {
    const controls = Array.isArray(payload?.trust_proof?.controls) ? payload.trust_proof.controls : [];
    const map = new Map();
    for (const control of controls) {
      map.set(String(control?.control || "").toLowerCase(), control || {});
    }
    return map;
  }

  function deriveRagProofChain(payload = {}) {
    const controls = controlLookup(payload);
    const evidenceMode = deriveEvidenceMode(payload);
    const baseNodes = [
      ["identity", "Identity", "identity", true, "#identity-session"],
      ["policy", "Policy", "policy", true, "#policy-enforcement"],
      ["retrieval-boundary", "Retrieval Boundary", "retrieval", true, "#retrieval-boundaries"],
      ["source-boundary", "Source Boundary", "retrieval", true, "#retrieval-boundaries"],
      ["secrets", "Secrets", "evidence provenance", true, "#evidence-integrity"],
      ["telemetry", "Telemetry", "audit", true, "#audit-replay"],
    ];

    const nodes = baseNodes.map(([id, label, controlKey, required, fallbackHref]) => {
      const control = controls.get(controlKey) || {};
      const nodeReason =
        id === "source-boundary" && !control.reason
          ? "The system could not prove that retrieved data stayed inside the allowed tenant/source boundary."
          : control.reason || "No explicit proof reason supplied.";
      return {
        id,
        label,
        required,
        status: mapControlStatus(control.status, required),
        evidenceMode: normalizeEvidenceMode(control.evidence_mode || evidenceMode),
        reason: nodeReason,
        proofHref: control.proof_href || fallbackHref,
      };
    });

    const requiredFails = nodes.filter((node) => node.required && node.status === "FAIL");
    const requiredUnknown = nodes.filter((node) => node.required && node.status === "UNKNOWN");
    let gateStatus = "PASS";
    let gateReason = "Upstream required controls passed.";
    if (requiredFails.length) {
      gateStatus = "FAIL";
      gateReason = `Required controls failed: ${requiredFails.map((node) => node.label).join(", ")}.`;
    } else if (requiredUnknown.length || evidenceMode !== "LIVE") {
      gateStatus = "WARN";
      gateReason =
        requiredUnknown.length > 0
          ? `Required controls are unknown: ${requiredUnknown.map((node) => node.label).join(", ")}.`
          : "Live production proof is not fully established.";
    }

    nodes.push({
      id: "launch-gate",
      label: "Launch Gate",
      required: true,
      status: gateStatus,
      evidenceMode,
      reason: gateReason,
      proofHref: "#launch-gate",
    });
    return nodes;
  }

  function deriveLaunchDecisionHeader(payload = {}) {
    const evidenceMode = deriveEvidenceMode(payload);
    const sourceDecision = String(payload?.readiness?.decision || "").toUpperCase();
    const decisionMap = {
      GO: "GO",
      CONDITIONAL_GO: "CONDITIONAL",
      NO_GO: "NO-GO",
    };
    let decision = decisionMap[sourceDecision] || "UNKNOWN";
    if (decision === "GO" && evidenceMode !== "LIVE") {
      decision = "CONDITIONAL";
    }

    const runtime = "Onyx RAG";
    const topBlocker = String(payload?.readiness?.top_blocker || "").trim() || "No blocking control currently detected.";
    let requiredAction = "Run a governed proof refresh and remediate failing required controls.";
    if (decision === "GO") {
      requiredAction = "Maintain monitoring and evidence retention.";
    } else if (topBlocker.toLowerCase().includes("retrieval")) {
      requiredAction = "Prove retrieval and source boundary controls with current governed evidence.";
    } else if (topBlocker.toLowerCase().includes("policy")) {
      requiredAction = "Policy decision could not be verified, so the gate failed closed.";
    } else if (evidenceMode !== "LIVE") {
      requiredAction = "Live runtime proof is not available, so production launch is not approved.";
    }

    const lastProvenAt = payload?.readiness?.last_updated || null;
    return {
      decision,
      runtime,
      evidenceMode,
      topBlocker,
      requiredAction,
      lastProvenAt,
    };
  }

  function getLiveOnyxProjectMap() {
    return [
      { path: "/onyx", description: "Onyx runtime source" },
      { path: "/trust", description: "Trust control-plane root" },
      { path: "/trust/frontend/main-dashboard", description: "Reviewer dashboard" },
      { path: "/trust/backend/api_gateway", description: "Dashboard/API gateway" },
      { path: "/trust/launch-gate", description: "Launch readiness gate" },
      { path: "/trust/evidence", description: "Readiness evidence artifacts" },
      { path: "/trust/policies", description: "Policy-as-code controls" },
      { path: "/trust/telemetry", description: "Telemetry and audit readiness" },
    ];
  }

  function deriveOnyxRuntimeStatus(payload = {}, evidenceMode = "UNKNOWN") {
    const onyx = (payload?.runtime_portfolio?.runtimes || []).find((item) => String(item?.runtime_key || "").toLowerCase() === "onyx") || {};
    const runtimeStatus = String(onyx?.status || "").toLowerCase();
    const readinessMessage = String(payload?.onyx_security_readiness?.message || "").toLowerCase();
    const topBlocker = String(payload?.readiness?.top_blocker || "").toLowerCase();

    if (evidenceMode === "DEMO") {
      return "DEMO";
    }
    if (evidenceMode === "SAMPLE") {
      return "SAMPLE";
    }
    if (runtimeStatus === "critical") {
      return "BLOCKED";
    }
    if (readinessMessage.includes("unreachable") || topBlocker.includes("unreachable")) {
      return "BLOCKED";
    }
    if (runtimeStatus === "healthy") {
      return evidenceMode === "LIVE" ? "CONNECTED" : "PARTIAL";
    }
    if (runtimeStatus === "warning") {
      return "PARTIAL";
    }
    if (evidenceMode === "PARTIAL") {
      return "PARTIAL";
    }
    return "UNKNOWN";
  }

  function deriveOnyxControlStatus(payload = {}, runtimeStatus = "UNKNOWN", evidenceMode = "UNKNOWN") {
    const launchPath = getGovernedOnyxLaunchPath(payload);
    const decision = String(payload?.readiness?.decision || "").toUpperCase();
    const hasGovernedPath = launchPath.startsWith("/launch/onyx");

    if (!hasGovernedPath) {
      return "Not wired yet";
    }
    if (decision === "GO" && evidenceMode === "LIVE" && runtimeStatus === "CONNECTED") {
      return "Launch-gated";
    }
    if (evidenceMode === "LIVE" || evidenceMode === "PARTIAL" || runtimeStatus === "PARTIAL") {
      return "Readiness-only";
    }
    if (runtimeStatus === "UNKNOWN" || evidenceMode === "UNKNOWN") {
      return "Unknown";
    }
    return "Direct link only";
  }

  function deriveLiveOnyxProject(payload = {}, launchHeader = null) {
    const header = launchHeader || deriveLaunchDecisionHeader(payload);
    const evidenceMode = deriveOnyxEvidenceMode(payload);
    const runtimeStatus = deriveOnyxRuntimeStatus(payload, evidenceMode);
    const directOnyxAppUrl = getConfiguredOnyxAppUrl(payload);
    const governedLaunchPath = getGovernedOnyxLaunchPath(payload);
    const controlStatus = deriveOnyxControlStatus(payload, runtimeStatus, evidenceMode);

    return {
      runtimeName: "Onyx RAG",
      runtimeSource: "/onyx",
      trustRoot: "/trust",
      dashboardPath: "/trust/frontend/main-dashboard",
      apiGatewayPath: "/trust/backend/api_gateway",
      launchGatePath: "/trust/launch-gate",
      evidencePath: "/trust/evidence",
      policiesPath: "/trust/policies",
      telemetryPath: "/trust/telemetry",
      folderMap: getLiveOnyxProjectMap(),
      onyxBaseUrlEnv: "CONTROL_PLANE_ONYX_BASE_URL",
      onyxAppUrlEnv: "CONTROL_PLANE_ONYX_APP_URL",
      onyxApiBaseUrlEnv: "CONTROL_PLANE_ONYX_API_BASE_URL",
      readinessEndpoint: "/api/security/readiness",
      overviewEndpoint: "/api/control-plane/overview",
      liveLogEndpoint: "/api/control-plane/live-log",
      directOnyxAppUrl,
      governedLaunchPath,
      controlStatus,
      runtimeStatus,
      status: runtimeStatus,
      evidenceMode,
      lastCheckedAt: payload?.readiness?.last_updated || null,
      explanation:
        "Onyx is the governed RAG runtime. Trust is the security, policy, evidence, telemetry, and launch-readiness layer around it.",
      governedLaunchNote:
        "Direct Onyx app URL opens the runtime. Governed Trust launch path records and enforces readiness decisions when backend launch-gate enforcement is wired.",
      controlPlaneScopeNote:
        "/onyx and /trust are sibling root-level folders. /onyx is not physically inside /trust.",
    };
  }

  function buildLaunchGatePacket(payload = {}) {
    const header = deriveLaunchDecisionHeader(payload);
    const liveOnyxProject = deriveLiveOnyxProject(payload, header);
    const proofChain = deriveRagProofChain(payload);
    const failingControls = proofChain.filter((node) => node.required && node.status === "FAIL").map((node) => node.label);
    const unknownControls = proofChain.filter((node) => node.required && node.status === "UNKNOWN").map((node) => node.label);
    const toStatus = (id) => proofChain.find((node) => node.id === id)?.status || "UNKNOWN";
    const evidenceLinks = (payload?.sources || []).map((source) => ({
      label: source?.label || "Evidence",
      href: source?.href || "",
    }));
    const modeNote =
      header.evidenceMode === "LIVE"
        ? "Evidence mode is LIVE."
        : `Evidence mode is ${header.evidenceMode}; this packet is not production launch approval proof.`;

    return {
      generatedAt: new Date().toISOString(),
      decision: header.decision,
      runtime: header.runtime,
      evidenceMode: header.evidenceMode,
      topBlocker: header.topBlocker,
      requiredAction: header.requiredAction,
      lastProvenAt: header.lastProvenAt,
      liveOnyxProject,
      proofChain,
      trustScorecard: {
        controls: Array.isArray(payload?.trust_proof?.controls) ? payload.trust_proof.controls.length : 0,
        deniedEvents: payload?.security_posture?.denied_events_count || 0,
      },
      failingControls,
      unknownControls,
      retrievalBoundaryStatus: toStatus("retrieval-boundary"),
      sourceBoundaryStatus: toStatus("source-boundary"),
      evidenceLinks,
      runtimePosture: payload?.readiness?.decision || "UNKNOWN",
      apiEndpointsUsed: ["/api/control-plane/overview", "/api/control-plane/live-log", "/api/security/readiness"],
      notes: [modeNote],
    };
  }

  const model = {
    getConfiguredOnyxAppUrl,
    getGovernedOnyxLaunchPath,
    deriveEvidenceMode,
    deriveOnyxEvidenceMode,
    deriveOnyxControlStatus,
    deriveOnyxRuntimeStatus,
    deriveRagProofChain,
    deriveLaunchDecisionHeader,
    deriveLiveOnyxProject,
    getLiveOnyxProjectMap,
    getProjectFolderMap: getLiveOnyxProjectMap,
    buildLaunchGatePacket,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = model;
  }
  globalScope.DashboardDecisionModel = model;
})(typeof window !== "undefined" ? window : globalThis);
