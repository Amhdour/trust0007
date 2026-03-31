# Client Template Kit

This repository can now be used as a repeatable client delivery template for AI Trust & Security Readiness work across three tracks: Layer Retrofit, Secure Starter Kit, and Launch Gate.

## What the template gives you

- A dashboard-first trust and security control plane
- A lighter client-facing explanation page
- Governed runtime handoff proof
- A trace-linked evidence model
- Launch-gate readiness framing
- A reusable overlay scaffold for per-client customization

Onyx is the default reference runtime in this repo, but the template is designed so the governed runtime profile can be swapped for another RAG or agent runtime per client.

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

The generated output is a client-specific overlay scaffold with placeholders and governance structure, not a reused proof bundle.

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

## Expected deliverables per engagement

- Technical review dashboard
- Client overview
- Evidence bundle
- Launch-gate report and readiness artifacts

## Suggested workflow

1. Generate a fresh client overlay scaffold.
2. Rename and brand the client-facing page and dashboard copy.
3. Replace identity, policy, retrieval, secrets, and readiness placeholders with client-specific decisions.
4. Decide whether the engagement is demo-only, live-proof, or launch-gate focused.
5. Reset or redirect artifacts before generating client-facing proof.

## Important caution

Do not present existing repo artifacts as client proof. The template is reusable, but proof must be regenerated for each engagement under that client's own identity, policy, retrieval, runtime, and launch conditions.

The scaffold does not claim live readiness by default. It only becomes client-credible proof when the generated overlay is wired to that client's real identity, policy, retrieval, secret, runtime, trace, and launch-gate path.
