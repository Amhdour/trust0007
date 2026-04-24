# Dashboard Visual Proof

This guide gives reviewers a fast visual companion for the strict live governed path.

For command-by-command execution, use [reviewer-runbook.md](reviewer-runbook.md). For the overall checklist, use [strict-live-proof-matrix.md](strict-live-proof-matrix.md).

## Illustrative vs. literal (read this first)

- The SVGs in this document are **illustrative review aids**.
- They are **not literal runtime screenshots** from your current environment.
- Treat strict live tests + governed artifacts as proof authority.

## Visual Previews

These SVGs show the cues to compare against live artifacts/tests:

- passing strict-live flow: [dashboard-live-pass.svg](images/dashboard-live-pass.svg)
- denied strict-live flow: [dashboard-live-deny.svg](images/dashboard-live-deny.svg)

## Current RAG launch-readiness surfaces

The main dashboard now includes a reviewer-first RAG safety strip near the top:

- **Launch Decision Header** (GO / NO-GO / CONDITIONAL / UNKNOWN)
- **Evidence mode badge** (`LIVE`, `PARTIAL`, `DEMO`, `SAMPLE`, `UNKNOWN`)
- **Live Onyx Project** mapping (`/onyx` runtime + `/trust` control plane)
- **RAG Proof Chain** (Identity → Policy → Retrieval Boundary → Source Boundary → Secrets → Telemetry → Launch Gate)
- **Why not GO?** fail-closed rationale
- **Download Launch Gate Packet** export bundle

Interpretation rule: if evidence mode is not `LIVE`, reviewers should treat the page as non-production proof and avoid production launch approval.

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
2. Check Launch Decision Header and Live Onyx Project (including `/onyx` and `/trust` sibling-root mapping).
3. Use artifact links for the corresponding trace.
4. Use strict live tests as final proof authority.

## Evidence authority note

Treat visuals as orientation only. The authoritative proof is:

- strict live tests
- governed flow artifacts
- reviewer evidence bundle
- proof matrix
