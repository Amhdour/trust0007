# Career Prototype Roadmap (AI Trust & Security Readiness Engineer)

This repository is a strong prototype platform for your stated direction:

- **Layer Retrofit**
- **Secure Starter Kits**
- **Launch Gates**

It already models governed runtime handoff, fail-closed controls, evidence artifacts, and readiness decisioning for Onyx runtime lanes.

## Can you use this repo to study + reverse engineer + build prototypes?

**Yes.** This repo is well-suited for that goal if you treat it as a hands-on lab and keep a disciplined learning loop:

1. Read architecture + request-flow docs.
2. Run governed paths in demo and live-like modes.
3. Break controls intentionally and observe deny/evidence behavior.
4. Add one control at a time and validate with tests/evidence.
5. Package each outcome as portfolio-grade proof (artifact + write-up + remediation).

## 90-day skill-building plan

## Days 1–30: Foundations and mental model

- Trace end-to-end request flow from dashboard -> governance -> runtime handoff.
- Map each control family to code and tests:
  - policy-as-code
  - retrieval boundaries
  - agent tool/MCP governance
  - telemetry/evidence integrity
  - launch-gate scoring/blockers
- Build a personal “control map” document for quick interview storytelling.

## Days 31–60: Adversarial validation and readiness hardening

- Create red-team scenarios for:
  - retrieval overreach/data boundary bypass attempts
  - unauthorized tool/MCP server use
  - secret unavailability and policy engine degradation
- Verify fail-closed behavior and collect evidence for each scenario.
- Improve test coverage for high-risk deny paths before adding new features.

## Days 61–90: Portfolio conversion and client-style packaging

- Create 3 showcase tracks aligned to your identity:
  1. **Layer Retrofit**: integrate Trust controls over an existing Onyx deployment.
  2. **Secure Starter Kit**: minimal deployable governed baseline for a new tenant.
  3. **Launch Gates**: policy + evidence threshold design with explicit GO/NO-GO criteria.
- Publish repeatable runbooks and “proof packs” (commands, artifacts, screenshots, lessons).
- Add a short architecture narrative for non-technical stakeholders.

## Recommended operating cadence (weekly)

- 1 design review (threat model + control intent)
- 2 implementation sessions (small scoped changes)
- 1 adversarial test session (deny-path validation)
- 1 evidence/report session (artifact quality + story clarity)

## What to build next (high-impact prototype backlog)

1. **Eval/Red-Team CI Gate**: attach evaluation metrics and attack outcomes as first-class readiness evidence.
2. **Policy Drift Guard**: CI rule that blocks merges on unreviewed policy bundle drift.
3. **MCP Trust Registry**: explicit registry + risk scoring for approved MCP servers/tools.
4. **Incident Drill Packs**: scripted outages (Vault/OPA/Onyx unavailable) with expected gate behavior and recovery evidence.
5. **Executive Readiness View**: concise dashboard panel translating technical controls into launch-risk language.

## Career leverage strategy

- Keep your work **evidence-first**:
  - problem statement
  - control design
  - attack simulation
  - pass/fail result
  - remediation and retest
- Use this format per project to create a high-signal portfolio aligned with enterprise AI governance roles.

## Practical caution

- This repo includes multiple vendored/upstream components; verify each component license and contribution boundaries before commercial redistribution.
- Keep secrets/tokens out of committed artifacts and sanitize evidence before publishing.
