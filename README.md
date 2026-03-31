# AI Trust & Security Stack Control Plane

This repository is a **dashboard-first AI Trust & Security control plane**. It proves a governed runtime handoff into Onyx, a strict live governed path, dependency-specific fail-closed behavior, and evidence-backed launch readiness without treating every vendored upstream as equally active.

The homepage is a repo-owned **Trust & Security Operations Dashboard for RAG and Autonomous Agents**. Onyx is the governed runtime plane behind that dashboard, not the primary visible product entry. This dashboard is the trust/security control plane that decides whether, how, and with what evidence access to Onyx is allowed.

Suggested short repository description:
`Dashboard-first AI Trust & Security Stack Control Plane for governed AI runtime launch readiness, policy enforcement, evidence integrity, and auditable Onyx handoffs.`

## What This Repo Proves

- A strict live governed path can allow a runtime handoff only after live identity, live policy, live retrieval, conditional live secret access, trace correlation, and launch-gate evidence all succeed.
- The same governed path fails closed when Keycloak-compatible identity, OPA, Qdrant, Vault, or trace/evidence requirements fail.
- The dashboard and artifact set explain why the handoff passed, denied, or downgraded.
- The dashboard can show recent governed requests as sanitized previews with trace-linked evidence, without exposing raw transcript content in the main reviewer view.
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

## Client Overview

If you need the simplest presentation layer first:

- client-facing page: `/client-overview`
- explainer notes: [docs/client-overview.md](/workspaces/beta011/docs/client-overview.md)
- technical dashboard: `/`

The client overview is intentionally lighter than the technical dashboard. It explains what the system checks, what it blocks, why that matters, and whether it looks safe to use now, while linking back to the technical proof.

## Client Template Mode

This repository can now act as a reusable client delivery template for AI Trust & Security Readiness engagements, not just a single working project.

It supports three repeatable engagement tracks:

- Layer Retrofit
- Secure Starter Kit
- Launch Gate

Onyx remains the default reference runtime used in this repo, but the client-template model is meant to support other governed RAG or agent runtimes as well.

- template guide: [docs/client-template-kit.md](/workspaces/beta011/docs/client-template-kit.md)
- engagement tracks: [docs/client-engagement-tracks.md](/workspaces/beta011/docs/client-engagement-tracks.md)
- tokenized scaffold: [overlays/client-template/README.md](/workspaces/beta011/overlays/client-template/README.md)
- stripped template readme: [README.template.md](/workspaces/beta011/README.template.md)

Materialize a client-ready overlay scaffold:

```bash
make init-client-template CLIENT_NAME="Acme Health" CLIENT_SLUG=acme-health ENGAGEMENT_TRACK=layer-retrofit PRIMARY_RUNTIME=Onyx
```

That generates `overlays/client-acme-health/` with tokenized client profile, policy, retrieval, identity, secrets, runtime, observability, and launch-gate scaffolds.

It scaffolds governance structure and placeholders only. It does not overwrite the current `myStarterKit` baseline, reuse prior client evidence, or claim live readiness by default.

The intended client-facing outputs are a technical review dashboard, a lighter client overview, an evidence bundle, and launch-gate artifacts that can be regenerated per engagement.

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

- flagship denied `/launch/onyx` handoff: [denied-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-flow.json)
- identity denial: [denied-identity-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- OPA denial/unavailable: [denied-opa-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- retrieval denial: [denied-retrieval-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- secret denial: [denied-secret-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
- launch-gate no-go from missing live evidence: [live-launch-gate-downgrade.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

The main fail-closed test coverage is in [tests/integration/test_strict_live_http_end_to_end.py](/workspaces/beta011/tests/integration/test_strict_live_http_end_to_end.py) and [tests/integration/test_live_governed_runtime_dependencies.py](/workspaces/beta011/tests/integration/test_live_governed_runtime_dependencies.py).

## Evidence Artifacts To Inspect

Primary governed-flow artifacts:

- [governed-request-feed.json](/workspaces/beta011/overlays/myStarterKit/artifacts/governed-request-feed.json)
- [governed-flow-summary.json](/workspaces/beta011/overlays/myStarterKit/artifacts/governed-flow-summary.json)
- [identity-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/identity-evidence.json)
- [policy-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/policy-evidence.json)
- [retrieval-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/retrieval-evidence.json)
- [secret-evidence.json](/workspaces/beta011/overlays/myStarterKit/artifacts/secret-evidence.json)
- [audit-records.jsonl](/workspaces/beta011/overlays/myStarterKit/artifacts/audit-records.jsonl)
- [trace-correlation.json](/workspaces/beta011/overlays/myStarterKit/artifacts/trace-correlation.json)
- [launch-gate-result.json](/workspaces/beta011/overlays/myStarterKit/artifacts/launch-gate-result.json)
- [reviewer evidence bundle](/workspaces/beta011/evidence/reviewer_evidence_bundle.json)

Panel evidence sources:

- Recent Governed Requests: `governed-request-feed.json` plus per-trace history snapshots under `overlays/myStarterKit/artifacts/governed-request-history/`
- Identity & Session: `identity-evidence.json` plus `trace-correlation.json`
- Policy Enforcement: `policy-evidence.json` plus governed events
- Retrieval Boundaries: `retrieval-evidence.json` plus governed events
- Secret Access: `secret-evidence.json`
- Audit & Replay: `audit-records.jsonl` when present, otherwise clearly labeled adapter-derived reconstruction from governed events
- Trace Correlation: `trace-correlation.json`
- Onyx Runtime: `governed-flow-summary.json`, `audit-records.jsonl`, and inspectable allow/deny bundles

Request visibility note:

- The dashboard surfaces sanitized governed request previews and hashes, not raw Onyx chat transcript replay.
- This feature does not persist full raw prompt text into the main dashboard payload or reviewer-safe request feed.

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
- Treat `upstream/*` as vendored third-party source snapshots tracked by this repository.
- Treat `overlays/myStarterKit` as the only currently managed git submodule checkout.
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
- `upstream/`: vendored copies of Keycloak, Envoy, Onyx, OPA, Vault, Qdrant, optional gVisor, Langfuse, Grafana, and Superset sources tracked by the main repo checkout.
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

Checkout/source-management state is locked in `evidence/upstream.lock.json`. Reviewer-facing classification for the dashboard lives in `evidence/upstream_usage.inventory.json`, `scripts/validate-upstream-state.py` checks that both views stay aligned, `scripts/list-upstream-groups.py` prints the default versus opt-in checkout sets, `scripts/record-upstream-refresh.py` records vendored upstream ref/commit refreshes back into the lock file, `scripts/sync-upstream-pins-from-checkout.py` captures snapshot fingerprints and available git pins, and `scripts/stage-default-upstream-checkout.py` stages a default-only upstream tree when you want opt-in components left out physically.

- Active now:
  - Onyx is the governed runtime target behind `/launch/onyx`.
  - Langfuse is a supporting evidence-plane activity source the dashboard can consume live.
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

See `docs/upstream-usage-matrix.md` for the reviewer-facing explanation, `evidence/upstream.lock.json` for the checkout/source lock, and `evidence/upstream_usage.inventory.json` for the machine-readable inventory surfaced by the dashboard.
See `docs/strict-live-proof-matrix.md` for the acceptance criteria and pass/fail proof matrix for the strict live governed path.

## Runtime Testing Model

- `Onyx` is the primary sample runtime platform for real integration testing in this repo.
- The in-repo demo is the fast fallback path when the upstream Onyx stack is not running.
- The dashboard remains the product entrypoint, and Onyx is the governed runtime plane reached behind it through governed handoffs.
- **Governance enforcement** is now live: `/launch/onyx` blocks denied requests with audit trails.

## Proof And Dashboard Docs

- [docs/client-overview.md](/workspaces/beta011/docs/client-overview.md): client-facing explanation layer and how it maps back to the technical dashboard
- [docs/reviewer-fast-path.md](/workspaces/beta011/docs/reviewer-fast-path.md): shortest path to see a pass, a deny, and a no-go
- [docs/strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md): acceptance criteria and dependency-by-dependency proof matrix
- [docs/dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md): what to look for in the dashboard for pass and deny cases
- [docs/control-plane-dashboard-homepage.md](/workspaces/beta011/docs/control-plane-dashboard-homepage.md): dashboard structure and data sourcing
