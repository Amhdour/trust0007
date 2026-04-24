# trust0007 — Trust Readiness Dashboard for the Onyx RAG Project

![CI](https://github.com/Amhdour/trust0007/actions/workflows/ci.yml/badge.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![Policy as Code](https://img.shields.io/badge/policy-OPA%20Rego-7A2CF4)

This repository demonstrates a production-style operating model where **Onyx RAG is the governed runtime** and **Trust is the readiness control plane** proving whether Onyx can launch safely.

## Career positioning

Core offers:

- **Layer Retrofit**
- **Secure Starter Kits**
- **Launch Gates**

Capability domains:

- AI Security Evals & Red Teaming
- Policy-as-Code & Runtime Guardrails
- Retrieval Security & Data Boundary Design
- Agent/MCP governance (deferred from current Onyx RAG launch scope)
- Telemetry, Auditability & Incident Readiness

## Repository layout

- `trust/` is the primary runnable project root for this repository.
- Root-level `.devcontainer` and `Makefile` act as reviewer-friendly wrappers and entry points.

## Reviewer fast path

```bash
make help
make test
make up-dev
```

Primary dashboard URL after boot: `http://127.0.0.1:3000`

Codespaces startup now auto-runs the stack and auto-opens the dashboard preview on port `3000`.

## Can you see Onyx in the Trust dashboard?

Yes. In the dashboard, open **Onyx RAG Access** and verify the **Onyx Security Readiness** block.

Expected behavior:

- In a healthy wired environment, decision is one of `APPROVED` or `CONDITIONAL`.
- If Onyx is unreachable, status safely degrades to `UNKNOWN` and the dashboard remains available.

Quick verification commands:

```bash
make verify-remote-onyx
make verify-live
make preflight-onyx-trust
```

If all pass, reload `http://127.0.0.1:3000` and confirm the **Onyx Security Readiness** panel is populated.

## Architecture (60-second view)

```text
Dashboard/UI (port 3000)
        |
        v
Governed launch lane (/launch/onyx)
        |
        v
Identity -> Policy (OPA) -> Retrieval Boundary -> Source Boundary -> Secret Health -> Telemetry -> Launch Gate
        |
        v
Telemetry + Evidence -> Launch Gate Decision -> Onyx Runtime Handoff
```

## Production-grade vs mocked boundaries

| Area | Current state | Portfolio reviewer note |
|---|---|---|
| Governance routing (`/launch/onyx`, `/launch/onyx/agent`) | Production-oriented in this repo | Fail-closed behavior is covered by integration tests/docs |
| Policy engine (OPA/Rego) | Production-oriented | Rego tests run in CI and local checks |
| Runtime dependency wiring (remote Onyx) | Production-oriented with env wiring | Verify via `make verify-remote-onyx` |
| Some fixtures/evidence samples | Mocked/static fixtures included | Used to keep demos deterministic and reproducible |
| Upstream submodules (`upstream/*`) | Reference/optional for local prototyping | Core trust control-plane logic remains first-class in `trust/` |

## Codex-ready reviewer prompt

Use this reusable prompt when asking Codex/agents for a reviewer-grade pass:

- `docs/CODEX_REVIEW_PROMPT.md`

## Where to go next

- Architecture and runtime controls: `trust/README.md`
- Career framing summary: `CAREER_PROJECT.md`
- CI gates: `.github/workflows/ci.yml`
- Release proof-pack automation: `.github/workflows/release-proof-pack.yml`
- Onyx integration details: `trust/docs/onyx-integration.md`

## External staging proof link (recommended)

When an external staging deployment is available, publish one canonical proof URL here for reviewers (for example a signed artifact bundle or immutable object-store link).  
Suggested placeholder format:

- `https://<your-staging-proof-host>/trust0007/<release-tag>/reviewer-proof-pack.tgz`
