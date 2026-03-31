# Docs

See `repo-bootstrap-assessment.md` for the initial repository map, architecture summary,
phased implementation plan, and first-file bootstrap sequence.

Additional homepage-focused notes:

- `client-overview.md`: simple explanation layer for clients and non-technical stakeholders, with a route-level page at `/client-overview`.
- `reviewer-fast-path.md`: shortest path to the passing live proof, denied live proofs, and launch-gate no-go proof.
- `dashboard-visual-proof.md`: lightweight visual guide showing what reviewers should look for in passing and denied live dashboard views.
- `control-plane-dashboard-homepage.md`: current homepage information architecture, plain-language first-layer rules, top-summary versus drilldown rules, terminology mapping, and demo-versus-live guidance.
- `submodules.md`: overlay submodule handling and vendored upstream tracking model.
- `upstream-usage-matrix.md`: strict classification of active, partial, optional, and reference-only upstream integrations.
- `live-vs-demo-matrix.md`: exact differences between fallback demo mode and strict live governed mode.
- `evidence-model.md`: what artifacts are emitted, how they correlate, and which ones are mandatory in live mode.
- `strict-live-proof-matrix.md`: acceptance criteria plus the pass/fail proof matrix for the strict live governed path.
- `operator-reviewer-quickstart.md`: quickest path to verify the governed flow, dashboard panels, and reviewer evidence bundle.
