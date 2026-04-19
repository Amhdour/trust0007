# Dify Runtime Integration (myStarterKit Controls)

## Purpose
`/launch/dify` provides a governed control-plane handoff for the Dify runtime lane, parallel to Onyx.

## Role in this repository
- Dify is treated as the autonomous-agent runtime lane.
- Onyx remains the governed RAG runtime lane.
- The dashboard remains the product entrypoint and policy/evidence authority.

## Governance focus
- Onyx lane emphasis: retrieval boundaries and data-path governance.
- Dify lane emphasis: tool authorization, MCP/server allowlists, and agent capability gating.

## Runtime proof posture
- Dify handoffs still use identity, policy, retrieval, secret, trace, and launch-gate checks from the shared governed flow.
- Runtime reachability is recorded in handoff outcomes and shown in dashboard runtime links.

## Entrypoint defaults and env overrides
- Default governed Dify handoff path: `/launch/dify?path=/apps` (workspace variant: `&mode=live&view=embedded`).
- Default Dify runtime port: `8088`.
- Set `CONTROL_PLANE_DIFY_PORT` to change the runtime port used by governed handoff reachability checks and redirects.
- Set `CONTROL_PLANE_DIFY_SECRET_PATH` when the Dify live handoff should read runtime secrets from a non-default Vault path.

## Guardrails
- Keep runtime governance in repo-owned control-plane logic.
- Keep evidence, audit, and launch-gate patterns runtime-neutral where practical.
- Add runtime-specific controls only where behavior truly differs.
