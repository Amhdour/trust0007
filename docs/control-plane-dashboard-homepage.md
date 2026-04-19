# Onyx Readiness Dashboard Homepage

## Architecture intent

The dashboard now follows a strict three-layer information architecture:

1. **Homepage = decision surface**
   - answers only:
     - Is Onyx ready now?
     - Why should I trust that answer?
     - What security control is failing?
2. **Drill-down = evidence**
   - technical proof for approved control domains
3. **Secondary pages/blocks = supporting context**
   - useful background that should not overload the homepage

## Homepage (decision-first)

The homepage should stay compact and reviewer-friendly:

- Minimal hero with current readiness signal
- Three primary panels:
  - **Onyx Readiness**
  - **Trust Proof**
  - **Security Posture**
- Compact **Trust Scorecard** for core controls:
  - Identity
  - Policy
  - Retrieval
  - Tool Governance
  - Audit
  - Launch Gate

These elements are intentionally the first and most prominent items on the page.

## Drill-down sections (evidence-first)

Only the approved drill-down set is emphasized in main navigation:

- `launch-gate`
- `entry-points`
- `policy-enforcement`
- `retrieval-boundaries`
- `tool-mcp-governance`
- `audit-replay`

These sections are where raw links, deeper control details, and technical diagnostics live.

## Secondary context (demoted from homepage core)

The following content remains accessible but no longer leads the homepage:

- reading-guide style explainer content
- compare/walkthrough storytelling blocks
- upstream posture depth and broad inventory context
- asset-coverage depth
- broad activity feed prominence
- client-overview explanatory lane as a primary action

Secondary context is now linked from a dedicated supporting block and optional disclosures.

## Existing secondary destinations

- `/client-overview` for non-technical narrative context
- `/api/control-plane/upstream-usage` for machine-readable connected-system inventory
- `/api/control-plane/live-log` for optional activity monitoring

## Evidence continuity

Evidence access is preserved through:

- trust scorecard proof links
- drill-down sections
- source links in the footer

The key change is placement: **decision first, evidence second, supporting context third**.
