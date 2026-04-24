const test = require("node:test");
const assert = require("node:assert/strict");

const {
  deriveLaunchDecisionHeader,
  deriveRagProofChain,
  deriveLiveOnyxProject,
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
  assert.equal(liveProject.runtimeSource, "/onyx");
  assert.equal(liveProject.trustRoot, "/trust");
  assert.equal(liveProject.dashboardPath, "/trust/frontend/main-dashboard");
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
