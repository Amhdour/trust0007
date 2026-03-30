# Dashboard Visual Proof

This page gives reviewers a fast visual layer for the strict live governed path.

## Visual Previews

- passing strict live flow:
  - [dashboard-live-pass.svg](/workspaces/beta011/docs/images/dashboard-live-pass.svg)
- denied strict live flow:
  - [dashboard-live-deny.svg](/workspaces/beta011/docs/images/dashboard-live-deny.svg)

These are lightweight proof previews, not literal runtime screenshots. They highlight the exact dashboard cues a reviewer should look for.

## What To Look For In A Passing Live Flow

Open [dashboard-live-pass.svg](/workspaces/beta011/docs/images/dashboard-live-pass.svg) and look for:

- mode banner: `LIVE GOVERNED MODE`
- top command summary showing readiness, score, latest handoff, top failing control, and evidence freshness
- newest governed request spotlight with a trace-linked record
- primary pass / deny / generate actions near the top
- `Identity result`: `ALLOW`
- `Decision engine`: `OPA`
- `Latest retrieval result`: `ALLOW`
- `Secret fetched`: `yes`
- `Trace complete`: `yes`
- `Readiness status`: `GO`
- `Latest handoff`: `ALLOW`

These indicators correspond to the strict live pass artifact in [allowed-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/allowed-flow.json).

## What To Look For In A Denied Live Flow

Open [dashboard-live-deny.svg](/workspaces/beta011/docs/images/dashboard-live-deny.svg) and look for:

- mode banner: `LIVE GOVERNED MODE`
- top command summary showing `DENY` or `NO-GO`
- flagship denied `/launch/onyx` proof spotlight near the top
- one dependency card showing a fail state
- `Trace complete`: `no` or a dependency result showing `DENY`
- `Missing evidence`: non-zero when launch-gate blocked the flow
- `Latest handoff`: `DENY`
- `Readiness status`: `NO-GO`

These cues correspond to the denial and no-go artifacts under [evidence/reviewer/inspectable-live-runtime](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime).

## Which Artifacts Match The Visuals

- passing live flow:
  - [allowed-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
- denied identity:
  - [denied-identity-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
- denied OPA:
  - [denied-opa-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json)
- denied retrieval:
  - [denied-retrieval-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json)
- denied secret:
  - [denied-secret-flow.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json)
- launch-gate no-go:
  - [live-launch-gate-downgrade.json](/workspaces/beta011/evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

## Important Accuracy Note

The visuals are documentation aids. The real proof remains:

- the strict live proof matrix
- the integration tests
- the governed-flow artifacts
- the reviewer evidence bundle

Do not treat the visuals as stronger evidence than the underlying artifacts and tests.

## Viewer Lanes

The current dashboard hierarchy is intentionally split into:

- Reviewer View:
  - mode banner, command summary, flagship proof, launch posture, governed requests, evidence freshness, upstream posture
- Operator Drilldown:
  - identity, policy, retrieval, secret, audit, trace, and deeper inventories

Reviewers should not need the operator drilldown to understand the top-level state.
