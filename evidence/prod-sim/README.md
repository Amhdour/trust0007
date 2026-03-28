Prod-sim evidence captured on 2026-03-28 UTC from the hardened `control_plane` service defined in `compose/docker-compose.prod-sim.yml`.

Governed flow evidence:
- `governed-flow-response.json`: live response from `GET /api/control-plane/governed-flow` with `trace_id` `flow-144dbb81ae7f` and `request_id` `req-7436902878db`.
- `events.jsonl`: emitted governed-flow events from the prod-sim service, including `tool.execution_attempt` for the allowed `onyx` handoff path.
- `launch-gate-result.json`: launch-gate artifact returned by the prod-sim service, showing `decision: pass` and `score: 8/8`.

Handoff evidence:
- `launch-allow.html`: allowed handoff page from `GET /launch/onyx?path=/app`.
- `launch-deny.html`: denied handoff page from `GET /launch/onyx?path=/app/bypass`, showing real evaluator output with denial trace `flow-04bc78269869` and `policy.forbidden_content`.

Reviewer-facing manifests for these artifacts live under `evidence/reviewer/inspectable-live-runtime/`.
