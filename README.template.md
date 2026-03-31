# AI Trust & Security Readiness Starter Kit Template

This repository can be used as a reusable client starter kit for:

- Layer Retrofit
- Secure Starter Kits
- Launch Gates

It is built around a dashboard-first control plane, a client-facing overview, governed runtime handoffs, evidence-linked launch gates, and additive overlays instead of upstream forks.

## What To Reuse

- The control-plane dashboard and client overview
- The evidence model and reviewer bundle
- The governed request / launch-gate flow
- The additive overlay model under `overlays/`
- The vendored upstream tracking model and validation scripts

## What To Materialize Per Client

Create a new client overlay scaffold:

```bash
make init-client-template CLIENT_NAME="Acme Health" CLIENT_SLUG=acme-health ENGAGEMENT_TRACK=layer-retrofit PRIMARY_RUNTIME=Onyx
```

That creates `overlays/client-acme-health/` with tokenized identity, policy, retrieval, secrets, runtime, observability, and readiness scaffolds.

## Delivery Rule

Treat `demo` mode as a local iteration path only. Treat `live` mode as the client-credible proof path only when identity, policy, retrieval, secrets, trace correlation, runtime proof, and launch-gate evidence all line up for the same trace.

## Template References

- `docs/client-template-kit.md`
- `docs/client-engagement-tracks.md`
- `overlays/client-template/`
