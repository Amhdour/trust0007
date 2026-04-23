# Docs

Start with `trust-readiness-platform.md` for the repo-first architecture, product module boundaries, readiness state model, Onyx/Onyx Agent launch lanes, dashboard APIs, production hardening, threat model, and roadmap. Use `governed-runtime-repair.md` for the repair center diagnostics, bounded remediation policy, evidence/audit model, and Onyx/Onyx Agent repair flows.

See `repo-bootstrap-assessment.md` for the initial repository map, architecture summary,
phased implementation plan, and first-file bootstrap sequence.

Additional homepage-focused notes:

- `client-overview.md`: simple explanation layer for clients and non-technical stakeholders, with a route-level page at `/client-overview`.
- `reviewer-fast-path.md`: shortest path to the passing live proof, denied live proofs, and launch-gate no-go proof.
- `reviewer-runbook.md`: one-pass reviewer/operator checklist for live readiness, runtime-specific checks, and failure triage.
- `dashboard-visual-proof.md`: lightweight visual guide showing what reviewers should look for in passing and denied live dashboard views.
- `control-plane-dashboard-homepage.md`: current homepage information architecture, plain-language first-layer rules, top-summary versus drilldown rules, terminology mapping, and demo-versus-live guidance.
- `client-template-kit.md`: how to use this repo as a reusable client starter kit, what the init script generates, and what to customize per engagement.
- `client-engagement-tracks.md`: recommended service tracks for layer retrofit, secure starter kits, and launch-gate work.
- `submodules.md`: overlay submodule handling and vendored upstream tracking model.
- `upstream-usage-matrix.md`: strict classification of active, partial, optional, and reference-only upstream integrations.
- `live-vs-demo-matrix.md`: exact differences between fallback demo mode and strict live governed mode.
- `evidence-model.md`: what artifacts are emitted, how they correlate, and which ones are mandatory in live mode.
- `strict-live-proof-matrix.md`: acceptance criteria plus the pass/fail proof matrix for the strict live governed path.
- `operator-reviewer-quickstart.md`: quickest path to verify the governed flow, dashboard panels, and reviewer evidence bundle.
- `governed-runtime-repair.md`: repair center architecture for diagnosing runtime lane failures, planning safe remediations, policy-checking execution, and recomputing readiness without forcing GO.
