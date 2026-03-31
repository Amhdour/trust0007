# Client Template Kit

This repository can now be used as a repeatable client delivery template for AI Trust & Security readiness work.

## What the template gives you

- A dashboard-first trust and security control plane
- A lighter client-facing explanation page
- Governed runtime handoff proof
- A trace-linked evidence model
- Launch-gate readiness framing
- A reusable overlay scaffold for per-client customization

## What the init script generates

Run:

```bash
python scripts/init-client-template.py --client-name "Acme Health" --client-slug acme-health
```

That materializes `overlays/client-acme-health/` from `overlays/client-template/`.

Generated scaffold areas:

- `client-profile.json`
- `client.env.example`
- `identity/claims-map.json`
- `policy/runtime-governance.json`
- `retrieval/boundaries.json`
- `runtime/runtime-profile.json`
- `secrets/paths.json`
- `observability/evidence-profile.json`
- `readiness/launch-gate.json`
- `artifacts/README.md`

## What to customize per client

- Tenant naming and identity claims
- Policy surfaces, roles, and approved tools
- Retrieval boundaries, collections, and trust labels
- Secret paths and secret purpose naming
- Runtime branding and governed entry points
- Launch-gate thresholds and approval language
- Client-facing narrative and dashboard branding

## What to keep stable

- The additive overlay model
- The evidence correlation model
- The live-versus-demo distinction
- The reviewer-safe request feed pattern
- The launch-gate framing and fail-closed expectations

## Suggested workflow

1. Generate a fresh client overlay scaffold.
2. Rename and brand the client-facing page and dashboard copy.
3. Replace identity, policy, retrieval, secrets, and readiness placeholders with client-specific decisions.
4. Decide whether the engagement is demo-only, live-proof, or launch-gate focused.
5. Reset or redirect artifacts before generating client-facing proof.

## Important caution

Do not present existing repo artifacts as client proof. The template is reusable, but proof must be regenerated for each engagement under that client's own identity, policy, retrieval, runtime, and launch conditions.
