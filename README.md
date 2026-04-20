# AI Trust & Security Control Plane

This repository is a **dashboard-first AI Trust & Security control plane** for dual runtime governance. It proves governed runtime handoffs into **Onyx (RAG)** and **Dify (Autonomous Agents)**, a strict live governed path, dependency-specific fail-closed behavior, and evidence-backed launch readiness without treating every vendored upstream as equally active.

The homepage is a repo-owned **AI Trust & Security Dashboard for trust, security, and launch posture**. Onyx and Dify are governed runtime lanes behind that dashboard, not the primary visible product entry. This dashboard is the review/readiness/security surface that decides whether, how, and with what evidence runtime access is allowed.

Suggested short repository description:
`AI Trust & Security control plane for governed Onyx (RAG) and Dify (Autonomous Agents) handoffs, policy enforcement, evidence integrity, and launch posture.`

## Deployment Maturity at a Glance

Use this table to understand what is included in-repo versus what remains environment-owned:

| Operating mode | What this repo provides | What you must supply |
| --- | --- | --- |
| **Local/dev** (`make up-dev`) | Dashboard + wiring workflow for development/demo checks. | Real deployment hardening is not implied by dev mode alone. |
| **Live/staging validation** (`make bootstrap-live`, `make verify-live`, `make up-live`, strict tests) | Governed runtime handoff proof path with explicit env validation and fail-closed dependency checks. | Staging-grade infrastructure/runtime endpoints and valid credentials. |
| **Public/production** | Compose/bootstrap patterns and evidence-oriented tests for self-hosted deployment. | Environment-specific ingress, DNS/TLS, secrets operations, monitoring/ownership, and public hosting posture. |

Current maturity: **self-hosted runnable**, **live/staging verifiable**, **public deployment environment-specific (not bundled as always-on hosting)**.

Detailed guidance: [Deployment Maturity and Modes](#deployment-maturity-and-modes).

## What This Repo Proves

- Dashboard-first **Layer Retrofit** and **Secure Starter Kit** patterns for governed AI runtime adoption.
- A strict **Launch Gate** path: runtime handoff is allowed only after identity, policy, retrieval, conditional secret access, trace correlation, and launch-gate evidence succeed on the same governed flow.
- Runtime-class governance:
  - **Onyx (RAG):** retrieval security, tenant/source boundaries, and governed data access.
  - **Dify (Autonomous Agents):** tool authorization, MCP governance, and agent capability controls.
- Fail-closed behavior when Keycloak-compatible identity, OPA policy checks, retrieval boundaries, Vault-backed secrets, or required trace/evidence signals fail.
- Evidence-backed review surfaces for telemetry, auditability, policy reasons, and launch-readiness posture without exposing raw sensitive prompt/transcript content.

## Start here for reviewers

This project is a **dashboard-first trust control plane** with two governed runtime lanes:

- **Onyx = RAG** (`/launch/onyx`)
- **Dify = Autonomous Agents** (`/launch/dify`)

Quickest validation path:

1. Reviewer fast path (30-second audit route): [docs/reviewer-fast-path.md](docs/reviewer-fast-path.md)
2. Reviewer runbook (5-minute path): [docs/reviewer-runbook.md](docs/reviewer-runbook.md)
3. Visual proof cues (illustrative): [docs/dashboard-visual-proof.md](docs/dashboard-visual-proof.md)
4. Live startup/bootstrap commands:
   - `make bootstrap-live`
   - `make verify-live`
   - `make up-live`
5. Strict live tests:
   - `pytest -q tests/integration/test_strict_live_onyx_end_to_end.py`
   - `pytest -q tests/integration/test_strict_live_dify_end_to_end.py`
6. Strict proof matrix: [docs/strict-live-proof-matrix.md](docs/strict-live-proof-matrix.md)
7. Deployment story and operating modes: [Deployment Maturity at a Glance](#deployment-maturity-at-a-glance) and [Deployment Maturity and Modes](#deployment-maturity-and-modes)

High-value reviewer artifacts:

- pass: [allowed-flow.json](evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
- denied identity: [denied-identity-flow.json](evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- denied OPA: [denied-opa-flow.json](evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- denied retrieval: [denied-retrieval-flow.json](evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- denied secret: [denied-secret-flow.json](evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
- launch-gate no-go: [live-launch-gate-downgrade.json](evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

## Client Overview

If you need the simplest presentation layer first:

- client-facing page: `/client-overview`
- explainer notes: [docs/client-overview.md](docs/client-overview.md)
- technical dashboard: `/`

The client overview is intentionally lighter than the technical dashboard. It explains what the system checks, what it blocks, why that matters, and whether it looks safe to use now, while linking back to the technical proof.

## Client Template Mode

This repository can now act as a reusable client delivery template for AI Trust & Security Readiness engagements, not just a single working project.

It supports three repeatable engagement tracks:

- Layer Retrofit
- Secure Starter Kit
- Launch Gate

The client-template model is dual-runtime by default (Onyx for RAG and Dify for Autonomous Agents), while still supporting extensions to other governed runtimes.

- template guide: [docs/client-template-kit.md](docs/client-template-kit.md)
- engagement tracks: [docs/client-engagement-tracks.md](docs/client-engagement-tracks.md)
- tokenized scaffold: [overlays/client-template/README.md](overlays/client-template/README.md)
- stripped template readme: [README.template.md](README.template.md)

Materialize a client-ready overlay scaffold:

```bash
make init-client-template CLIENT_NAME="Acme Health" CLIENT_SLUG=acme-health ENGAGEMENT_TRACK=layer-retrofit PRIMARY_RUNTIME=Onyx
```

That generates `overlays/client-acme-health/` with tokenized client profile, policy, retrieval, identity, secrets, runtime, observability, and launch-gate scaffolds.

It scaffolds governance structure and placeholders only. It does not overwrite the current `myStarterKit` baseline, reuse prior client evidence, or claim live readiness by default.

The intended client-facing outputs are a technical review dashboard, a lighter client overview, an evidence bundle, and launch-gate artifacts that can be regenerated per engagement.

## Passing Strict Live Flow

The strongest “see a pass” path is:

- Onyx strict live test: [tests/integration/test_strict_live_onyx_end_to_end.py](tests/integration/test_strict_live_onyx_end_to_end.py)
  - `test_strict_live_onyx_handoff_passes_through_real_stack`
- Dify strict live test: [tests/integration/test_strict_live_dify_end_to_end.py](tests/integration/test_strict_live_dify_end_to_end.py)
  - `test_strict_live_dify_handoff_passes_with_runtime_specific_governance`
- proof summary: [docs/strict-live-proof-matrix.md](docs/strict-live-proof-matrix.md)
- reviewer artifact: [allowed-flow.json](evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
- dashboard visual callout: [docs/dashboard-visual-proof.md](docs/dashboard-visual-proof.md)

That path proves:

- Keycloak-compatible identity participation
- OPA decision participation
- Qdrant retrieval participation
- Vault-backed secret participation when required
- complete trace correlation
- launch-gate pass from live evidence
- governed runtime handoff approval (Onyx and Dify routes are enforced through the same control-plane model)

## Repeatable Live Staging Bootstrap

If you want to stand the governed live path up from scratch against real running dependencies, first create the staging-style env file and then use the repeatable bootstrap:

```bash
cp compose/.env.production.example compose/.env.production
make bootstrap-live
make smoke-live
```

For explicit runtime separation, keep local development on the default compose and use the live profile only with explicit live env values:

```bash
cp .env.live.example .env.live
make up-dev
make verify-live
make up-live
```

That workflow:

- starts `compose/docker-compose.production.yml`
- can enforce `compose/docker-compose.live.yml` + `.env.live` for fail-fast live env validation
- initializes and unseals non-dev Vault storage under `.runtime/live-governed/`
- imports or reuses the governed Keycloak realm
- applies a user-attribute-backed `tenant_id` mapper to the live web and smoke clients
- creates or refreshes the governed live bootstrap user
- seeds tenant-scoped Qdrant content and the required Vault runtime secret
- starts the dashboard stack in `live` / `staging` mode
- mints a real Keycloak token with `openid email profile`
- verifies governed live handoff and dashboard evidence (`/launch/onyx?path=/app&mode=live`, with governed `/launch/dify` surface support)

The precise claim after `make smoke-live` passes is: a staging-style governed live path is proven against a running Keycloak, OPA, Qdrant, and Vault stack. That is intentionally narrower and more accurate than claiming every supporting service or every runtime-health surface is fully production-ready.

For the full runbook, see [docs/staging-governed-stack.md](docs/staging-governed-stack.md).

## Minimum Serious Live Preview (Operator Definition)

For this repo, a truthful first live-preview claim is:

- dashboard/control-plane is enforcing governed live handoffs
- `/launch/onyx` and `/launch/dify` are both proven in live mode
- Keycloak + OPA + Qdrant + Vault are participating in the same governed flow
- current evidence artifacts are generated and visible to the dashboard

That claim is intentionally narrower than “all vendored upstreams are up.”

Required services for first proof:

- `control_plane`
- `keycloak` (+ `keycloak_db`)
- `opa`
- `qdrant`
- `vault`
- reachable Onyx runtime target (`/launch/onyx`)
- reachable Dify runtime target (`/launch/dify`)

Optional/supporting services:

- `langfuse` (evidence-plane destination)
- `grafana` (observability support)
- `envoy` (future ingress-depth; not required for today’s governed launch proof)

Reference-only / intentionally out of first-proof scope:

- vendored upstream trees not currently exercised by strict live governed tests
- optional platform depth (for example Superset or gVisor-based isolation) unless your environment explicitly needs them

Next milestone for external preview:

- one externally reachable staging deployment (outside localhost) that reproduces the same governed live proof for both Onyx and Dify lanes.


## Deployment Maturity and Modes

- **Local/dev mode (`make up-dev`)**: development and demo workflows; useful for UI and wiring checks, not sufficient alone for governed-live proof.
- **Live/staging validation mode (`make up-live` + bootstrap + smoke/tests)**: governed proof generation path with explicit live environment validation and dependency checks.
- **Public/production deployment**: this repo provides compose definitions, bootstrap scripts, and tests for self-hosted deployments. It does **not** include an always-on hosted production environment. Ingress, external DNS/TLS, secrets lifecycle, and operational ownership remain environment-specific.

Current maturity: **self-hosted runnable**, **live/staging verifiable**, **public deployment optional and environment-specific**.

For the one-pass reviewer/operator flow, see [docs/reviewer-runbook.md](docs/reviewer-runbook.md).

## Failing Strict Live Flow Examples

The strongest “see a deny” and “see a no-go” paths are:

- flagship denied governed handoff proof: [denied-flow.json](evidence/reviewer/inspectable-live-runtime/denied-flow.json)
- identity denial: [denied-identity-flow.json](evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- OPA denial/unavailable: [denied-opa-flow.json](evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- retrieval denial: [denied-retrieval-flow.json](evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- secret denial: [denied-secret-flow.json](evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
- launch-gate no-go from missing live evidence: [live-launch-gate-downgrade.json](evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

The main fail-closed test coverage is in [tests/integration/test_strict_live_onyx_end_to_end.py](tests/integration/test_strict_live_onyx_end_to_end.py), [tests/integration/test_strict_live_dify_end_to_end.py](tests/integration/test_strict_live_dify_end_to_end.py), and [tests/integration/test_live_governed_runtime_dependencies.py](tests/integration/test_live_governed_runtime_dependencies.py).

## Evidence Artifacts To Inspect

Primary governed-flow artifacts (generated under `overlays/myStarterKit/artifacts/` after live bootstrap):

- `governed-request-feed.json`
- `governed-flow-summary.json`
- `identity-evidence.json`
- `policy-evidence.json`
- `retrieval-evidence.json`
- `secret-evidence.json`
- `audit-records.jsonl`
- `trace-correlation.json`
- `launch-gate-result.json`
- [reviewer evidence bundle](evidence/reviewer_evidence_bundle.json)

Panel evidence sources:

- Recent Governed Requests: `governed-request-feed.json` plus per-trace history snapshots under `overlays/myStarterKit/artifacts/governed-request-history/`
- Identity & Session: `identity-evidence.json` plus `trace-correlation.json`
- Policy Enforcement: `policy-evidence.json` plus governed events
- Retrieval Boundaries: `retrieval-evidence.json` plus governed events
- Secret Access: `secret-evidence.json`
- Audit & Replay: `audit-records.jsonl` when present, otherwise clearly labeled adapter-derived reconstruction from governed events
- Trace Correlation: `trace-correlation.json`
- Runtime Lanes (Onyx + Dify): `governed-flow-summary.json`, `audit-records.jsonl`, and inspectable allow/deny bundles

Request visibility note:

- The dashboard surfaces sanitized governed request previews and hashes, not raw runtime transcript replay.
- This feature does not persist full raw prompt text into the main dashboard payload or reviewer-safe request feed.

## What Is Mandatory Now

When `CONTROL_PLANE_GOVERNANCE_MODE=live` or a request uses `mode=live`, a governed handoff to `/launch/onyx` or `/launch/dify` fails closed unless all of these complete successfully:

1. Keycloak-backed identity from bearer token or session cookie
2. OPA decision for the request
3. Retrieval against the configured live backend
4. Required Vault-backed secret access
5. Complete trace correlation across the governed flow
6. Launch-gate approval from live evidence

Runtime entrypoint configuration (explicit env vars):

- `CONTROL_PLANE_ONYX_PORT` (default `3010`) controls the governed `Onyx` runtime target for `/launch/onyx`.
- `CONTROL_PLANE_DIFY_PORT` (default `8088`) controls the governed `Dify` runtime target for `/launch/dify`.
- `CONTROL_PLANE_ONYX_SECRET_PATH` and `CONTROL_PLANE_DIFY_SECRET_PATH` can override runtime-specific Vault secret paths for live handoff checks.

## What Is Proven Now

- Proven mandatory path elements in the governed live flow:
  - Onyx and Dify handoffs behind the dashboard
  - Keycloak-compatible identity
  - OPA policy decision
  - Qdrant retrieval
  - Vault secret access when required
  - trace correlation
  - live-evidence launch gate
- Precise current claim:
  - the governed live path is proven
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

## What Is Not Yet Fully Proven

- The repo should not claim that every supporting service or every runtime-health surface is fully live-ready just because the governed live handoff is passing.
- In containerized local setups where Onyx runs outside the compose network, runtime-local health proof can remain partial even when the governed live chain is passing. That is why `overlays/myStarterKit/artifacts/onyx-runtime-proof.json` can still show visibility caveats while the live launch gate is passing.
- The repo still needs one externally reachable staging or production deployment outside localhost before it should be described as a true live product workflow.

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
- `upstream/`: vendored copies of Keycloak, Envoy, Onyx, OPA, Vault, Qdrant, optional gVisor, Langfuse, Dify, Grafana, and Superset sources tracked by the main repo checkout.
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

## Development vs Live Staging

**Development stack** (current default):
```bash
docker-compose -f compose/docker-compose.yml up
```
- Keycloak/Vault in dev mode
- Localhost-only service exposure
- Development defaults for rapid iteration

**Live staging stack** (real dependency path):
```bash
bash scripts/bootstrap-live-governed-path.sh
```
- `compose/docker-compose.production.yml`
- non-dev Keycloak and Vault initialization
- user-attribute tenant claims instead of a hardcoded tenant mapper
- real-stack smoke test and `live_stack` pytest coverage

## Upstream integration model

Not every vendored upstream under `upstream/` is an equally active part of the current architecture.

Checkout/source-management state is locked in `evidence/upstream.lock.json`. Reviewer-facing classification for the dashboard lives in `evidence/upstream_usage.inventory.json`, `scripts/validate-upstream-state.py` checks that both views stay aligned, `scripts/list-upstream-groups.py` prints the default versus opt-in checkout sets, `scripts/record-upstream-refresh.py` records vendored upstream ref/commit refreshes back into the lock file, `scripts/sync-upstream-pins-from-checkout.py` captures snapshot fingerprints and available git pins, and `scripts/stage-default-upstream-checkout.py` stages a default-only upstream tree when you want opt-in components left out physically.

- Active now:
  - Onyx (RAG) and Dify (Autonomous Agents) are governed runtime lanes behind `/launch/onyx` and `/launch/dify`.
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

- `Onyx` and `Dify` are governed runtime lanes in this control plane (RAG and Autonomous Agents respectively).
- Onyx remains the deepest sample runtime path in current integration tests, while Dify is a governed first-class launch surface in the control plane.
- The in-repo demo remains the fast fallback path when full upstream runtime stacks are not running.
- The dashboard remains the product entrypoint, and both runtimes are reached only through governed handoffs.
- **Governance enforcement** is now live: `/launch/onyx` and `/launch/dify` block denied requests with audit trails.

## Proof And Dashboard Docs

- [docs/client-overview.md](docs/client-overview.md): client-facing explanation layer and how it maps back to the technical dashboard
- [docs/reviewer-fast-path.md](docs/reviewer-fast-path.md): shortest path to see a pass, a deny, and a no-go
- [docs/strict-live-proof-matrix.md](docs/strict-live-proof-matrix.md): acceptance criteria and dependency-by-dependency proof matrix
- [docs/dashboard-visual-proof.md](docs/dashboard-visual-proof.md): what to look for in the dashboard for pass and deny cases
- [docs/control-plane-dashboard-homepage.md](docs/control-plane-dashboard-homepage.md): dashboard structure and data sourcing
