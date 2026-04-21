# Governed Runtime Repair

Governed Runtime Repair is the diagnostic and bounded-remediation subsystem for the Onyx and Dify runtime lanes. It is designed for broken launch readiness, not for bypassing readiness. The module detects what is unhealthy, explains the evidence behind the finding, proposes policy-checked actions, executes only approved bounded actions, writes audit/evidence records, and recomputes readiness afterward.

## Trust And Safety Constraints

- Repair is deny-by-default.
- Repair never forces a lane, portfolio, or launch gate to GO.
- Repair never bypasses policy, identity, secret, retrieval, or MCP/tool controls.
- Repair never weakens tool allowlists or MCP restrictions.
- Repair never fabricates runtime continuity proof.
- Demo-only evidence is surfaced as a blocker for live readiness.
- Every diagnostic and remediation emits structured audit/evidence.
- Destructive or state-changing actions require policy approval.
- Production repair actions are more restrictive than local or staging.

## Runtime Lanes

### Onyx

The Onyx diagnostic adapter checks runtime target configuration, local/public route reachability, governed handoff result, continuity proof after handoff, retrieval boundary proof, dependency health, evidence freshness, and launch-gate consistency.

It distinguishes local reachable/public unreachable, route alive but governed entry failing, governed handoff allowed without continuity proof, stale/absent retrieval proof, and contradictions between launch gates and runtime state.

### Dify

The Dify diagnostic adapter checks workspace/app route reachability, governed handoff result, MCP server and tool posture, privileged tool approval requirements, dependency evidence, freshness, launch-gate consistency, and route/config drift.

Dify is treated as a governed execution plane. Tool and MCP posture failures are repair findings, not invitations to loosen policy.

## Remediation Actions

Safe initial actions:

- `recheck_health`
- `reprobe_routes`
- `retry_governed_handoff`
- `refresh_runtime_proof`
- `refresh_evidence_bundle`
- `re_evaluate_launch_gate`
- `validate_runtime_config`
- `validate_dependency_connectivity`
- `mark_lane_degraded`
- `quarantine_lane`
- `surface_precise_blocker`

Approval-gated actions:

- `restart_local_service`
- `reload_runtime_config`
- `rotate_nonhuman_runtime_credential`
- `reseed_nonprod_test_data`
- `resync_policy_bundle`

The current implementation records approval-gated external actions as policy decisions and skips local execution unless the action has a bounded in-process handler. This keeps repair from becoming a blind restart button.

## Approval Model

Repair policy lives in `policies/control-plane/default-governance-policy.json` under `repair_actions`.

Important rules:

- route reprobe and evidence refresh are allowed in all environments
- local service restart is only allowed in dev/staging and still requires approval
- credential rotation requires approval
- production policy-bundle resync requires an elevated role such as `repair_admin` or `security_admin`
- failed launch gates can only be re-evaluated from fresh evidence, never overridden

## Evidence And Audit Model

Repair writes diagnostic reports, remediation plans, repair runs, repair events, and append-only audit records under `overlays/myStarterKit/artifacts/`.

Required repair event fields include `event_type`, `repair_run_id`, `correlation_id`, `tenant_id`, `actor_id`, `lane`, `runtime_id`, `decision_id`, `action_id`, `result`, `reason_codes`, timestamps, freshness, trace links, and source references.

## Readiness Impact

After repair execution or dry run, readiness is recomputed through the existing trust-readiness model. Repair does not write readiness states directly.

Rules enforced by diagnostics and readiness recomputation:

- critical continuity failure means the lane is not READY
- failed launch gate means not GO
- demo-only evidence means not GO for live readiness
- stale critical evidence means not GO
- contradictory panel states are surfaced as `LAUNCH_GATE` or `CONFIG_DRIFT` findings
- quarantine creates an active incident control and recomputes the lane as `INCIDENT_MODE`

## API

POST endpoints:

- `/repair/diagnose/onyx`
- `/repair/diagnose/dify`
- `/repair/plan/onyx`
- `/repair/plan/dify`
- `/repair/execute/onyx`
- `/repair/execute/dify`

GET endpoints:

- `/api/repair/center`
- `/repair/runs`
- `/repair/runs/{run_id}`
- `/repair/plans/{plan_id}`

Each endpoint returns correlation IDs, lane, readiness impact, audit/evidence references, a human-readable summary, and machine-readable details.

Example dry run:

```bash
curl -sS -X POST http://localhost:3000/repair/execute/onyx \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"tenant-stage","actor_id":"operator-a","dry_run":true}'
```

Example approved quarantine:

```bash
curl -sS -X POST http://localhost:3000/repair/execute/onyx \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"tenant-stage","actor_id":"security-admin","actor_roles":["repair_admin"],"action_id":"quarantine_lane","approved_actions":["quarantine_lane"]}'
```

## Safe Vs Blocked Examples

Safe examples include route reprobe, evidence refresh, launch-gate re-evaluation from current evidence, and surfacing a precise blocker.

Blocked or approval-gated examples include production restarts, policy resync without elevated role, credential rotation without explicit approval, treating demo evidence as live proof, and forcing GO after a failed launch gate.
