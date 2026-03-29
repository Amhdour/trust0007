# Reviewer Fast Path

This page is the fastest way to inspect what the repo proves without reading the whole codebase.

## 30-Second Path

1. Read the proof contract:
   - [strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md)
2. Open the main integrated proof test:
   - [test_strict_live_http_end_to_end.py](/workspaces/beta011/tests/integration/test_strict_live_http_end_to_end.py)
3. Inspect one passing live artifact:
   - [allowed-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
4. Inspect one denied live artifact:
   - [denied-identity-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
5. Inspect one launch-gate no-go artifact:
   - [live-launch-gate-downgrade.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

## See A Pass

Use this path when you want the strongest positive proof:

- test:
  - [test_strict_live_http_end_to_end.py](/workspaces/beta011/tests/integration/test_strict_live_http_end_to_end.py)
  - `test_strict_live_handoff_passes_through_http_dependency_chain`
- reviewer artifact:
  - [allowed-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
- raw artifacts:
  - [governed-flow-summary.json](/workspaces/beta011/overlays/myStarterKit/artifacts/governed-flow-summary.json)
  - [identity-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/identity-evidence.json)
  - [policy-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/policy-evidence.json)
  - [retrieval-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/retrieval-evidence.json)
  - [secret-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/secret-evidence.json)
  - [trace-correlation.json](/workspaces/beta011/overlays/myStarterKit/artifacts/trace-correlation.json)
  - [launch-gate-result.json](/workspaces/beta011/overlays/myStarterKit/artifacts/launch-gate-result.json)
- visual guide:
  - [dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md)

What this proves:

- live Keycloak-compatible identity participated
- live OPA participated
- live Qdrant participated
- live Vault participated when required
- trace correlation completed
- launch-gate used live evidence and passed
- governed Onyx handoff was approved
- the dashboard can show a sanitized governed request preview linked back to the same trace and artifact set

What this does not prove:

- Envoy is mandatory in the current request path
- Grafana or Langfuse are fail-closed dependencies
- the stack is production complete

## See A Deny

Use these for dependency-specific fail-closed proof:

- identity deny:
  - [denied-identity-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- OPA deny:
  - [denied-opa-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- retrieval deny:
  - [denied-retrieval-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- secret deny:
  - [denied-secret-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)

What each proves:

- the dependency participated in the strict live path
- failure was observable
- failure blocked the handoff
- the artifacts and dashboard explain why

## See Launch-Gate No-Go

Use this when you want to inspect live evidence failure rather than a direct dependency outage:

- reviewer artifact:
  - [live-launch-gate-downgrade.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)
- proof matrix row:
  - [strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md)
- dashboard visual guide:
  - [dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md)

This proves that missing live evidence or incomplete trace continuity can still block the governed handoff.

## Request Visibility

Use this when you want reviewer-safe visibility into what entered the governed path without dumping raw prompts:

- dashboard section:
  - `Recent Governed Requests`
- feed artifact:
  - [governed-request-feed.json](/workspaces/beta011/overlays/myStarterKit/artifacts/governed-request-feed.json)
- latest summary:
  - [governed-flow-summary.json](/workspaces/beta011/overlays/myStarterKit/artifacts/governed-flow-summary.json)

What this shows:

- sanitized question preview
- allow or deny status
- live versus demo evidence mode
- reason codes
- trace-linked artifact references

What this does not show:

- full conversation history
- raw prompt dumps in the main dashboard view

## Mandatory Vs Supporting

- Proven mandatory path elements:
  - Keycloak-compatible identity
  - OPA policy decision
  - Qdrant retrieval
  - Vault secret access when required
  - trace correlation
  - live-evidence launch gate
  - governed Onyx handoff
- Active supporting elements:
  - Envoy
  - Grafana
  - Langfuse
- Optional future:
  - Superset
  - gVisor
- Reference-only:
  - Keycloak Quickstarts
  - OPA Envoy Plugin
  - Langfuse Python SDK

## Portfolio Framing

This repo is strongest as proof of:

- Layer Retrofit:
  - repo-owned governance added over runtime and platform components without pretending they are all equally integrated
- Secure Starter Kits:
  - additive local control-plane logic over vendored and overlay assets
- Launch Gates:
  - evidence-backed readiness with fail-closed live dependency participation
