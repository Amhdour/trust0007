const test = require("node:test");
const assert = require("node:assert/strict");

const {
  deriveOnyxEvidenceMode,
  deriveOnyxRuntimeStatus,
  deriveLaunchDecisionHeader,
  deriveRagProofChain,
  deriveLiveReadinessRubric,
  deriveRealityGap,
  deriveLiveOnyxProject,
  getLiveOnyxProjectMap,
  buildLaunchGatePacket,
} = require("./decision-model.js");

test("deriveLaunchDecisionHeader prevents GO when evidence is demo", () => {
  const header = deriveLaunchDecisionHeader({
    readiness: { decision: "GO", evidence_mode: "demo", top_blocker: "", last_updated: "2026-04-24T00:00:00Z" },
  });
  assert.equal(header.decision, "CONDITIONAL");
  assert.equal(header.evidenceMode, "DEMO");
});

test("deriveRagProofChain marks launch gate fail when required control fails", () => {
  const chain = deriveRagProofChain({
    readiness: { evidence_mode: "live" },
    trust_proof: {
      controls: [
        { control: "Identity", status: "PASS" },
        { control: "Policy", status: "PASS" },
        { control: "Retrieval", status: "MISSING_PROOF" },
        { control: "Audit", status: "PASS" },
      ],
    },
  });
  const launchGate = chain.find((node) => node.id === "launch-gate");
  assert.equal(launchGate.status, "FAIL");
});

test("deriveLiveOnyxProject keeps /onyx and /trust mapping", () => {
  const liveProject = deriveLiveOnyxProject({ readiness: { evidence_mode: "sample" } });
  assert.equal(liveProject.runtimeName, "Onyx RAG");
  assert.equal(liveProject.runtimeSource, "/onyx");
  assert.equal(liveProject.trustRoot, "/trust");
  assert.equal(liveProject.dashboardPath, "/trust/frontend/main-dashboard");
  assert.equal(liveProject.apiGatewayPath, "/trust/backend/api_gateway");
});

test("getLiveOnyxProjectMap includes required root and dashboard folders", () => {
  const paths = getLiveOnyxProjectMap().map((item) => item.path);
  assert.ok(paths.includes("/onyx"));
  assert.ok(paths.includes("/trust"));
  assert.ok(paths.includes("/trust/frontend/main-dashboard"));
});

test("deriveOnyxRuntimeStatus degrades when readiness evidence is unreachable", () => {
  const status = deriveOnyxRuntimeStatus(
    {
      readiness: { evidence_mode: "live", top_blocker: "Onyx readiness endpoint unreachable" },
      runtime_portfolio: { runtimes: [{ runtime_key: "onyx", status: "healthy" }] },
    },
    "LIVE",
  );
  assert.equal(status, "BLOCKED");
});

test("deriveOnyxEvidenceMode keeps demo/sample from appearing live", () => {
  assert.equal(deriveOnyxEvidenceMode({ readiness: { evidence_mode: "demo" } }), "DEMO");
  assert.equal(deriveOnyxEvidenceMode({ readiness: { evidence_mode: "sample" } }), "SAMPLE");
});

test("buildLaunchGatePacket includes proof chain and live project mapping", () => {
  const packet = buildLaunchGatePacket({
    readiness: { decision: "NO_GO", evidence_mode: "unknown", top_blocker: "Missing policy proof" },
  });
  assert.equal(packet.decision, "NO-GO");
  assert.ok(Array.isArray(packet.proofChain));
  assert.equal(packet.liveOnyxProject.runtimeSource, "/onyx");
  assert.equal(packet.liveOnyxProject.trustRoot, "/trust");
  assert.ok(packet.readinessRubric);
  assert.ok(packet.realityGap);
});

test("deriveLiveReadinessRubric requires fresh live proof and passing required controls", () => {
  const rubric = deriveLiveReadinessRubric(
    {
      readiness: {
        decision: "GO",
        evidence_mode: "live",
        last_updated: "2026-04-25T11:30:00Z",
      },
      trust_proof: {
        freshness_sla: { stale_after_hours: 4, expired_after_hours: 8 },
        controls: [
          { control: "Identity", status: "PASS" },
          { control: "Policy", status: "PASS" },
          { control: "Retrieval", status: "PASS" },
          { control: "Evidence Provenance", status: "PASS" },
          { control: "Audit", status: "PASS" },
        ],
      },
    },
    null,
    null,
    new Date("2026-04-25T12:00:00Z"),
  );
  assert.equal(rubric.freshnessStatus, "FRESH");
  assert.equal(rubric.liveEligible, true);
});

test("deriveRealityGap flags drift between declared mode and observed mode", () => {
  const header = deriveLaunchDecisionHeader({
    readiness: { decision: "GO", evidence_mode: "sample", last_updated: "2026-04-25T11:00:00Z" },
    data_mode: { label: "live" },
  });
  const rubric = deriveLiveReadinessRubric(
    {
      readiness: { decision: "GO", evidence_mode: "sample", last_updated: "2026-04-25T11:00:00Z" },
      data_mode: { label: "live" },
    },
    header,
    null,
    new Date("2026-04-25T12:00:00Z"),
  );
  const gap = deriveRealityGap(
    {
      data_mode: { label: "live" },
    },
    header,
    rubric,
  );
  assert.equal(gap.declaredMode, "LIVE");
  assert.equal(gap.observedEvidenceMode, "SAMPLE");
  assert.equal(gap.driftDetected, true);
});
