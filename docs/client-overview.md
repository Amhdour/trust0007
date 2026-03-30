# Client Overview

This project now includes a separate client-facing explanation layer at `/client-overview`.

## What it is for

The client overview is the simple visual entry point for:

- clients
- judges
- managers
- non-technical stakeholders
- first-meeting demos

It explains:

- what the system does
- what checks happen before AI access is allowed
- what gets blocked
- why blocked requests matter
- whether the system looks safe to use now

## What it includes

The page intentionally uses a lighter visual format than the technical dashboard:

- a traffic-light summary
- a simple safety-check process diagram
- a before-and-after comparison of direct AI access versus checked AI access
- one allowed example card
- one blocked example card
- a simple readiness gauge
- direct links to the technical dashboard and proof

## What it does not replace

The client overview does not replace:

- the technical dashboard
- the reviewer evidence bundle
- raw artifacts
- launch-gate reports
- trace-linked technical proof

It is a summary layer only.

## Accuracy rules

The client overview should stay truthful about:

- live versus demo evidence
- allowed versus blocked requests
- current readiness status
- the difference between summary and proof

It should never imply stronger production maturity than the technical dashboard or evidence actually supports.

## Mapping to the technical dashboard

- Client overview:
  - simple explanation
  - meeting-friendly visuals
  - fast state summary
- Technical dashboard:
  - deeper reviewer view
  - operator drilldowns
  - raw evidence links
  - trace IDs
  - policy source and path
  - reason codes
  - component inventories

## Current source signals

The client overview is based on real repository signals:

- `/api/control-plane/overview`
- `evidence/reviewer/inspectable-live-runtime/allowed-flow.json`
- `evidence/reviewer/inspectable-live-runtime/denied-flow.json`
- `launch-gate/starter_launch_readiness_report.json`

That means the simplified visuals stay tied to real governed-flow, blocked-access, proof, and readiness state.
