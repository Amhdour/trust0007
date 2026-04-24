const test = require("node:test");
const assert = require("node:assert/strict");

const {
  deriveOnyxEvidenceMode,
  deriveOnyxRuntimeStatus,
  deriveLaunchDecisionHeader,
  deriveRagProofChain,
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
});
