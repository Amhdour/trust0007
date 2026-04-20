# Dashboard Visual Proof

This guide gives reviewers a fast visual companion for the strict live governed path.

For command-by-command execution, use [reviewer-runbook.md](reviewer-runbook.md). For the overall checklist, use [strict-live-proof-matrix.md](strict-live-proof-matrix.md).

## Visual Previews (illustrative)

These SVGs are **illustrative review aids**, not literal runtime screenshots:

- passing strict-live flow: [dashboard-live-pass.svg](images/dashboard-live-pass.svg)
- denied strict-live flow: [dashboard-live-deny.svg](images/dashboard-live-deny.svg)

They show the dashboard cues a reviewer should verify against live artifacts/tests.

## What good looks like (passing visual cues)

Open [dashboard-live-pass.svg](images/dashboard-live-pass.svg) and verify:

- mode banner shows `LIVE GOVERNED MODE`
- command summary shows healthy readiness/score posture
- newest governed request includes a trace-linked record
- top links expose pass/deny/proof actions
- identity result is `ALLOW`
- decision engine is `OPA`
- retrieval result is `ALLOW`
- secret fetched is `yes`
- trace complete is `yes`
- readiness is `GO`
- latest handoff is `ALLOW`

Artifact match for this visual: [allowed-flow.json](../evidence/reviewer/inspectable-live-runtime/allowed-flow.json).

## Common failure signals (denied visual cues)

Open [dashboard-live-deny.svg](images/dashboard-live-deny.svg) and look for:

- mode banner still says `LIVE GOVERNED MODE`
- command summary flips to `DENY` and/or `NO-GO`
- denied governed runtime proof spotlight is visible
- one or more dependency cards show fail state
- trace completeness drops to `no` (or dependency denies)
- missing evidence count becomes non-zero
- latest handoff is `DENY`
- readiness is `NO-GO`

Related denial/no-go artifacts:

- [denied-identity-flow.json](../evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- [denied-opa-flow.json](../evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- [denied-retrieval-flow.json](../evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- [denied-secret-flow.json](../evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
- [live-launch-gate-downgrade.json](../evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

## Reviewer reading order

1. Check the homepage mode banner and command summary.
2. Check runtime portfolio and latest governed handoff.
3. Use artifact links for the corresponding trace.
4. Use strict live tests as final proof authority.

## Evidence authority note

Treat visuals as orientation only. The authoritative proof is:

- strict live tests
- governed flow artifacts
- reviewer evidence bundle
- proof matrix
