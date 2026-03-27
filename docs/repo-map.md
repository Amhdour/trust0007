# Repository Map

## Purpose
This document describes the umbrella repository layout for the AI Trust & Security stack.

## Top-level directories
- `.devcontainer/` — Codespaces and local dev environment definitions.
- `frontend/` — Dashboard-first control-plane UI.
- `backend/` — API gateway and posture/evidence aggregation services.
- `contracts/` — Dashboard and control-plane JSON schemas.
- `apps/` — Logical runtime and governance module grouping.
- `infra/` — Logical infrastructure grouping for identity, policy, retrieval, telemetry, and evidence systems.
- `evidence/` — Dashboard-owned evidence export area.
- `compose/` — Container composition and environment overlays.
- `docs/` — Architecture, boundaries, and operational documentation.
- `scripts/` — Validation/bootstrap helper scripts.
- `adapters/` — Integration adapters between upstream services.
- `policies/` — Policy artifacts (e.g., trust/security policy bundles).
- `telemetry/` — Observability configuration and dashboards.
- `launch-gate/` — Startup readiness and enforcement checks.
- `overlays/` — Local overlays/customizations layered over upstream components.
- `upstream/` — Third-party source mirrors/submodules.

## Notes
- `upstream/*` is treated as third-party and should remain unchanged unless strictly necessary.
- New implementation should be additive in umbrella-owned folders, with the dashboard homepage treated as the primary product surface.
