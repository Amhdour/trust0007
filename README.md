# AI Trust & Security Stack Control Plane

This repository is a **dashboard-first AI Trust & Security control plane**. It proves a governed runtime handoff into Onyx, a strict live governed path, dependency-specific fail-closed behavior, and evidence-backed launch readiness without treating every vendored upstream as equally active.

The homepage is a repo-owned **Trust & Security Operations Dashboard for RAG and Autonomous Agents**. Onyx is a governed runtime module behind that dashboard, not the primary visible product entry.

Suggested short repository description:
`Dashboard-first AI Trust & Security Stack Control Plane for governed AI runtime launch readiness, policy enforcement, evidence integrity, and auditable Onyx handoffs.`

## What This Repo Proves

- A strict live governed path can allow a runtime handoff only after live identity, live policy, live retrieval, conditional live secret access, trace correlation, and launch-gate evidence all succeed.
- The same governed path fails closed when Keycloak-compatible identity, OPA, Qdrant, Vault, or trace/evidence requirements fail.
- The dashboard and artifact set explain why the handoff passed, denied, or downgraded.
- The repo distinguishes mandatory path elements from supporting, optional, and reference-only components instead of inflating the architecture.

## Reviewer Fast Path

If you only have a minute, start here:

1. Proof matrix: [docs/strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md)
2. Main strict-live integration proof: [tests/integration/test_strict_live_http_end_to_end.py](/workspaces/beta011/tests/integration/test_strict_live_http_end_to_end.py)
3. Reviewer landing page: [docs/reviewer-fast-path.md](/workspaces/beta011/docs/reviewer-fast-path.md)
4. Passing live flow artifact: [allowed-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
5. Denied identity artifact: [denied-identity-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
6. Denied OPA artifact: [denied-opa-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
7. Denied retrieval artifact: [denied-retrieval-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
8. Denied secret artifact: [denied-secret-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
9. Launch-gate no-go artifact: [live-launch-gate-downgrade.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)
10. Visual dashboard proof guide: [docs/dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md)

## Passing Strict Live Flow

The strongest “see a pass” path is:

- test: [tests/integration/test_strict_live_http_end_to_end.py](/workspaces/beta011/tests/integration/test_strict_live_http_end_to_end.py)
  - `test_strict_live_handoff_passes_through_http_dependency_chain`
- proof summary: [docs/strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md)
- reviewer artifact: [allowed-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
- dashboard visual callout: [docs/dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md)

That path proves:

- Keycloak-compatible identity participation
- OPA decision participation
- Qdrant retrieval participation
- Vault-backed secret participation when required
- complete trace correlation
- launch-gate pass from live evidence
- governed Onyx handoff approval

## Failing Strict Live Flow Examples

The strongest “see a deny” and “see a no-go” paths are:

- identity denial: [denied-identity-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- OPA denial/unavailable: [denied-opa-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- retrieval denial: [denied-retrieval-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- secret denial: [denied-secret-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
- launch-gate no-go from missing live evidence: [live-launch-gate-downgrade.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

The main fail-closed test coverage is in [tests/integration/test_strict_live_http_end_to_end.py](/workspaces/beta011/tests/integration/test_strict_live_http_end_to_end.py) and [tests/integration/test_live_governed_runtime_dependencies.py](/workspaces/beta011/tests/integration/test_live_governed_runtime_dependencies.py).

## Evidence Artifacts To Inspect

Primary governed-flow artifacts:

- [governed-flow-summary.json](/workspaces/beta011/overlays/myStarterKit/artifacts/governed-flow-summary.json)
- [identity-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/identity-evidence.json)
- [policy-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/policy-evidence.json)
- [retrieval-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/retrieval-evidence.json)
- [secret-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/secret-evidence.json)
- [trace-correlation.json](/workspaces/beta011/overlays/myStarterKit/artifacts/trace-correlation.json)
- [launch-gate-result.json](/workspaces/beta011/overlays/myStarterKit/artifacts/launch-gate-result.json)
- [reviewer evidence bundle](/workspaces/beta011/evidence/reviewer_evidence_bundle.json)

## What Is Mandatory Now

When `CONTROL_PLANE_GOVERNANCE_MODE=live` or a request uses `mode=live`, a governed handoff to `/launch/onyx` fails closed unless all of these complete successfully:

1. Keycloak-backed identity from bearer token or session cookie
2. OPA decision for the request
3. Retrieval against the configured live backend
4. Required Vault-backed secret access
5. Complete trace correlation across the governed flow
6. Launch-gate approval from live evidence

## What Is Proven Now

- Proven mandatory path elements:
  - Onyx handoff behind the dashboard
  - Keycloak-compatible identity
  - OPA policy decision
  - Qdrant retrieval
  - Vault secret access when required
  - trace correlation
  - live-evidence launch gate
- Active supporting elements:
  - Langfuse
  - Envoy
  - Grafana
- Optional future elements:
  - Superset
  - gVisor
- Reference-only elements:
  - Keycloak Quickstarts
  - OPA Envoy Plugin
  - Langfuse Python SDK

## What Remains Supporting Or Future

- Envoy strengthens the ingress story, but the current proved request path does not require it.
- Grafana is a useful drill-down surface, but not a fail-closed dependency.
- Langfuse is active for observability, but live handoff proof does not depend on Langfuse reachability.
- Superset and gVisor remain future or optional depth.

## Design intent

- Lead with the dashboard, then identity/session, then governed AI runtime, then evidence/analytics.
- Treat `upstream/*` as vendored third-party source snapshots.
- Treat `overlays/myStarterKit` as the governance overlay baseline.
- Keep local platform logic additive in:
  - `frontend/`
  - `backend/`
  - `contracts/`
  - `apps/`
  - `infra/`
  - `evidence/`
  - `overlays/`
  - `adapters/`
  - `policies/`
  - `telemetry/`
  - `launch-gate/`
  - `compose/`
  - `docs/`
  - `scripts/`

## Current structure snapshot

- `frontend/main-dashboard/`: custom control-plane homepage and navigation shell.
- `backend/`: dashboard API gateway, posture aggregation, evidence, launch-gate, and integration services.
- `contracts/`: JSON schemas for posture, retrieval, tools inventory, eval, audit, and launch-gate views.
- `apps/`: logical runtime/governance grouping for Onyx and myStarterKit.
- `infra/`: logical mapping for identity, policy, retrieval, telemetry, and evidence systems.
- `evidence/`: dashboard-owned evidence export area.
- `upstream/`: vendored copies of Keycloak, Envoy, Onyx, OPA, Vault, Qdrant, optional gVisor, Langfuse, Grafana, and Superset sources.
- `overlays/myStarterKit/`: governance-overlay submodule.
- `overlays/governance-overlay/`: local, additive overlay contracts and integration wiring (this repo).
- `adapters/`: Python adapters for policy/runtime/retrieval/secrets/sandbox/observability bridges.
- `policies/`: OPA policy bundles and tests.
- `telemetry/`: event schema, sinks, exporters, and dashboard artifacts.
- `launch-gate/`: evidence-based readiness evaluator.
- `compose/`: local development stack definitions.
- `.devcontainer/`: Codespaces/devcontainer setup.

## Phase status

Execution plan tracking and phase notes are stored under `docs/phases/`.

## Quickstart

Run the minimal in-repo demo:

```bash
make demo
```

Validate the primary runtime integration target:

```bash
make test-onyx-target
```

Test governance enforcement (live artifacts + handoff blocking):

```bash
make test-governance
```

Run the full test suite:

```bash
make test
```

Serve the local control-plane dashboard API/UI shell:

```bash
make serve-dashboard
```

## Development vs Production Simulation

**Development stack** (current default):
```bash
docker-compose -f compose/docker-compose.yml up
```
- Keycloak/Vault in dev mode
- Localhost-only service exposure
- Development defaults for rapid iteration

**Production simulation** (hardened stack):
```bash
docker-compose -f compose/docker-compose.prod-sim.yml up
```
- Keycloak/Vault in production mode
- Security hardening (read-only filesystems, no-new-privileges)
- Proper initialization requirements
- External certificate/trust store support

## Upstream integration model

Not every vendored upstream under `upstream/` is an equally active part of the current architecture.

- Active now:
  - Onyx is the governed runtime target behind `/launch/onyx`.
  - Langfuse is the evidence-plane activity source the dashboard can consume live.
  - Keycloak, OPA, Qdrant, and Vault are now active in the strict live governed path, where live identity, live policy, live retrieval, and conditional live secret access are mandatory dependencies.
- Partially used:
  - Envoy and Grafana are kept because they strengthen real trust boundaries or control outcomes, but they are not yet mandatory request-path dependencies.
- Optional future:
  - Superset and gVisor remain in scope only as future analytics or isolation depth.
- Reference only:
  - Keycloak Quickstarts, the OPA Envoy Plugin, and the Langfuse Python SDK are retained as implementation references, not as active architecture claims.

Every component that remains in scope is expected to answer:

- what it does
- where it sits in the runtime
- why it is necessary
- what governance signal it emits
- what evidence artifact it contributes
- what control gap appears if it is removed

See `docs/upstream-usage-matrix.md` for the reviewer-facing explanation and `evidence/upstream_usage.inventory.json` for the machine-readable inventory surfaced by the dashboard.
See `docs/strict-live-proof-matrix.md` for the acceptance criteria and pass/fail proof matrix for the strict live governed path.

## Runtime Testing Model

- `Onyx` is the primary sample runtime platform for real integration testing in this repo.
- The in-repo demo is the fast fallback path when the upstream Onyx stack is not running.
- The dashboard remains the product entrypoint, and Onyx is the governed runtime reached behind it.
- **Governance enforcement** is now live: `/launch/onyx` blocks denied requests with audit trails.

## Proof And Dashboard Docs

- [docs/reviewer-fast-path.md](/workspaces/beta011/docs/reviewer-fast-path.md): shortest path to see a pass, a deny, and a no-go
- [docs/strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md): acceptance criteria and dependency-by-dependency proof matrix
- [docs/dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md): what to look for in the dashboard for pass and deny cases
- [docs/control-plane-dashboard-homepage.md](/workspaces/beta011/docs/control-plane-dashboard-homepage.md): dashboard structure and data sourcing
