# Control-Plane Dashboard Homepage

## What changed

The homepage was upgraded from a general control-plane shell into a reviewer-facing Trust & Security Operations Dashboard.

The page now leads with:

- operator briefing answers
- a flagship denied `/launch/onyx` proof path near the top
- governance KPI cards
- a dominant Security Readiness / Launch Gate panel
- explicit live-vs-demo and latest handoff pass/fail cues
- blocked and governed actions
- six primary trust/security domains
- asset and protection coverage
- evidence integrity and freshness
- governed Onyx runtime outcomes

## Homepage structure

1. Hero: repository positioning, data mode, runtime role, and high-level workflow.
   - explicit wording that Onyx is the governed runtime plane and the dashboard is the trust/security control plane
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
   - Secret Access
   - Tool / MCP Governance
   - Audit & Replay
   - Trace Correlation
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
  - enriched with repo-backed inventory coverage, runtime-path status, and dashboard-signal counts
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
- identity / policy / retrieval / secret / trace sections
  - `overlays/myStarterKit/artifacts/identity-evidence.json`
  - `overlays/myStarterKit/artifacts/policy-evidence.json`
  - `overlays/myStarterKit/artifacts/retrieval-evidence.json`
  - `overlays/myStarterKit/artifacts/secret-evidence.json`
  - `overlays/myStarterKit/artifacts/audit-records.jsonl`
  - `overlays/myStarterKit/artifacts/trace-correlation.json`
  - `overlays/myStarterKit/artifacts/governed-flow-summary.json`
- upstream posture
  - component inventory from `evidence/upstream_usage.inventory.json`
  - coverage audit from `backend/integration_adapter/repository.py`
  - reviewer-facing rationale rendered in `backend/posture_service/service.py`
- audit and reviewer evidence
  - `overlays/myStarterKit/artifacts/audit-records.jsonl` when a governed flow has run
  - adapter-derived audit reconstruction from the governed event feed only when no runtime-generated audit artifact exists yet
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
  - runtime-generated audit records when a governed flow has run
  - live identity, policy, retrieval, secret, and trace evidence panels when those artifacts exist
  - live-log polling from Onyx and Langfuse when reachable
- Demo-derived fallback:
  - `telemetry/exports/sample_events.jsonl`
  - any KPI or blocked-action summary built from that sample file when live governed-flow artifacts are absent

The dashboard should always make this visible through the data-mode badge in the hero area.
