# Control-Plane Dashboard Homepage

## What changed

The homepage was upgraded from a general control-plane shell into a plain-language safety and review dashboard.

It now has a companion client-facing explanation layer at `/client-overview` for non-technical audiences. That page summarizes the same system state with simpler visuals and links back into the technical dashboard when deeper inspection is needed.

The page now leads with:

- a plain-language first layer for non-technical readers
- a compact command summary instead of a long KPI wall
- a short “How to read this dashboard” guide near the top
- a prominent live-vs-demo mode banner with consequence text
- the newest governed request preview near the top
- one flagship denied `/launch/onyx` proof callout instead of repeated near-identical summaries
- direct pass / deny / generate actions
- reviewer and operator navigation lanes
- lighter homepage summaries for heavy inventories and tables
- collapsed sample tables for secondary depth
- reviewer-first proof sections before deeper operator diagnostics

## Homepage structure

1. Hero: repository positioning, data mode, runtime role, and high-level workflow.
   - explicit wording that Onyx is the governed runtime plane and the dashboard is the trust/security control plane
2. Mode banner: explicit `LIVE GOVERNED MODE` or `DEMO / FALLBACK MODE` framing with consequence text.
3. How to read this dashboard:
   - what the colors mean
   - the main questions the page answers
   - where the technical detail lives
4. Command summary:
   - readiness verdict
   - readiness score
   - latest handoff allow / deny
   - top failing control
   - evidence freshness summary
   - newest governed request spotlight
   - flagship denied `/launch/onyx` proof spotlight
   - primary actions
5. Plain-language review / technical-details lanes: clear split between simple safety meaning and deeper engineering proof.
6. Sticky tab groups:
   - Plain-Language Review
   - Technical Details
7. Drill-down sections grouped into:
   - Plain-Language Review
   - Big Picture
   - Recent Requests
   - What The System Stopped
   - Safety Check Before Use
   - AI System Access
   - How Reliable The Proof Is
   - Connected Parts Of The System
   - Technical Details
   - Who Is Trying To Use It
   - Rules Being Applied
   - What Information It Can Access
   - Protected Keys And Passwords
   - What Actions The AI Can Take
   - What Happened And How We Review It
   - Did We Follow The Full Process?
   - What The System Is Watching
8. Recent activity feed and raw source links.

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
- recent governed requests
  - `overlays/myStarterKit/artifacts/governed-request-feed.json`
  - per-trace snapshot artifacts under `overlays/myStarterKit/artifacts/governed-request-history/`
  - dashboard-visible question text comes from sanitized previews only
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

## Governed request visibility

- The homepage request feed is reviewer-safe operational evidence, not raw chat replay.
- Each row shows a sanitized question preview, governance outcome, evidence mode, and trace-linked artifact references.
- If a prompt contains likely secrets or sensitive tokens, the preview is redacted before it becomes dashboard-visible.

## Summary vs drilldown

- The homepage top area should answer the platform-state question in under 10 seconds.
- The first layer should read like a safety and review report, not like a backend console.
- The top command summary is for decisive state, not exhaustive evidence listing.
- Heavy inventories stay available, but the homepage now shows only high-signal slices, capped rows, and collapsed sample tables before deeper drill-through.
- Plain-language review sections prioritize proof posture, flagship pass/deny evidence, governed request visibility, and launch readiness.
- Technical-details sections prioritize diagnostics, trace continuity, auditability, and deeper control-domain inspection.

## Plain-Language Layer

- Non-technical readers should be able to understand the first layer without knowing terms like trace correlation, governed runtime, retrieval boundaries, or audit replay.
- The page therefore prefers:
  - simple display titles
  - plain-language summaries
  - human-readable status wording
  - short helper explanations
- The technical meaning is still preserved in:
  - lower technical sections
  - raw evidence links
  - trace IDs
  - policy source and path details
  - reason codes
  - machine-readable artifacts

## Terminology Mapping

| Technical term | Plain-language dashboard label |
| --- | --- |
| Launch gate | Safety check before use |
| Governed runtime / Onyx runtime | AI system access |
| Evidence integrity & freshness | How reliable the proof is |
| Upstream integration posture | Connected parts of the system |
| Identity & session | Who is trying to use it |
| Policy enforcement | Rules being applied |
| Retrieval boundaries | What information it can access |
| Secret access | Protected keys and passwords |
| Tool / MCP governance | What actions the AI can take |
| Audit & replay | What happened and how we review it |
| Trace correlation | Did we follow the full process? |

## Plain-language vs technical split

- Plain-Language Review should be enough to answer:
  - what is protected
  - what was blocked
  - why it was blocked
  - what evidence exists
  - whether the system is launch-ready
- Technical Details should be where you inspect:
  - identity/session detail
  - policy engine behavior
  - retrieval boundaries
  - secret posture
  - audit and trace linkage
  - deeper inventories

The same dashboard serves both audiences, but the technical path should never bury the plain-language fast path.
