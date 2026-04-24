# Client Engagement Tracks

This AI Trust & Security Readiness Starter Kit is best reused through three primary engagement tracks. Each track keeps the control-plane model stable while changing what gets customized first and what deliverables are emphasized.

## 1. Layer Retrofit

Use this when the client already has a RAG or agent runtime and needs governance added around it.

Primary goals:

- map trust boundaries
- add policy and retrieval guardrails
- introduce governed runtime handoff
- add trace, audit, and launch-gate proof

Overlay areas to customize first:

- `runtime/`
- `policy/`
- `retrieval/`
- `observability/`

## 2. Secure Starter Kit

Use this when the client needs a strong baseline quickly.

Primary goals:

- stand up a governed runtime baseline
- ship opinionated identity, policy, retrieval, and secrets patterns
- give stakeholders a dashboard and client overview immediately
- establish a reusable evidence model early

Overlay areas to customize first:

- `client-profile.json`
- `identity/`
- `policy/`
- `secrets/`
- `readiness/`

## 3. Launch Gate

Use this when the client already has most of the stack, but needs a credible go/no-go control and proof set before broader release.

Primary goals:

- define mandatory live controls
- prove fail-closed behavior
- tie readiness to evidence rather than opinion
- produce reviewer and executive-facing artifacts

Overlay areas to customize first:

- `readiness/`
- `observability/`
- `policy/`

## Supporting capability add-ons

These tracks can be extended with:

- AI security evals and red teaming
- policy-as-code and runtime guardrails
- retrieval security and data boundary design
- agent identity, tool authorization, and MCP hardening
- telemetry, auditability, and incident readiness

## Template rule

Keep the engagement track client-specific, but keep the control-plane architecture stable. The more repeatable your evidence model and launch-gate language are, the easier it becomes to scale this work across clients.
