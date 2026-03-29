# Control-Plane Dashboard Homepage

## What changed

The homepage was upgraded from a general control-plane shell into a reviewer-facing Trust & Security Operations Dashboard.

The page now leads with:

- operator briefing answers
- governance KPI cards
- a dominant Security Readiness / Launch Gate panel
- blocked and governed actions
- six primary trust/security domains
- asset and protection coverage
- evidence integrity and freshness
- governed Onyx runtime outcomes

## Homepage structure

1. Hero: repository positioning, data mode, runtime role, and high-level workflow.
2. Operator briefing: quick answers to what is protected, what was blocked, why, what evidence exists, and launch readiness.
3. Governance KPIs: policy, retrieval, tool, audit, evidence, and launch metrics.
4. Security Readiness / Launch Gate: readiness state, control-family summaries, top failing controls, residual risks, and evidence links.
5. Drill-down sections:
   - Operations Snapshot
   - Blocked / Governed Actions
   - Upstream Integration Posture
   - Identity & Session
   - Policy Enforcement
   - Retrieval Boundaries
   - Tool / MCP Governance
   - Audit & Replay
   - Launch Gate
   - Asset / Protection Coverage
   - Evidence Integrity & Freshness
   - Onyx Governed Runtime
6. Recent activity feed and raw source links.

## Where each panel gets its data

- `/api/control-plane/overview`
  - built in `backend/posture_service/service.py`
  - contract labels from `contracts/control-plane-dashboard.json`
- `/api/control-plane/upstream-usage`
  - built from `evidence/upstream_usage.inventory.json`
  - used to keep the dashboard's upstream posture section machine-readable and reviewer-auditable
- launch readiness
  - `backend/launch_gate_service/service.py`
  - `launch-gate/starter_launch_readiness_report.json`
  - overlay launch artifacts when present
- policy / asset / boundary coverage
  - runtime policy bundle from `overlays/myStarterKit/policies/bundles/default/policy.json`
  - fallback `policies/runtime-policy-fallback.json`
- blocked actions and governance KPIs
  - live governed flow artifacts when present
  - otherwise `telemetry/exports/sample_events.jsonl`
- audit and reviewer evidence
  - `evidence/reviewer_evidence_bundle.json`
  - `evidence/reviewer/inspectable-live-runtime/*.json`
  - `evidence/prod-sim/*`
- recent activity feed
  - `/api/control-plane/live-log`
  - Onyx container logs and Langfuse activity when available

## Real vs demo-derived

- Real or environment-derived:
  - policy bundle selection
  - service inventory
  - raw artifact existence checks
  - reviewer bundle links
  - launch-report parsing
  - live governed-flow artifacts when generated
  - live-log polling from Onyx and Langfuse when reachable
- Demo-derived fallback:
  - `telemetry/exports/sample_events.jsonl`
  - any KPI or blocked-action summary built from that sample file when live governed-flow artifacts are absent

The dashboard should always make this visible through the data-mode badge in the hero area.
