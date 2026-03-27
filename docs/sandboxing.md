# Risky-Execution Sandboxing Design

## Scope
Decision logic and integration points for sandboxing. This phase does **not** deploy full gVisor runtime infrastructure.

## When sandboxing is required
Sandbox mode is required when policy marks an execution as risky (e.g., risk score above threshold).
Typical triggers:
- risky action types (code execution, system modification, network probing),
- risky tools (`shell.exec`, `python.exec`, `container.exec`),
- user-supplied code,
- combined network/filesystem/external integration behaviors.

## What counts as risky execution
The policy evaluator computes a risk score from request attributes:
- action type,
- tool name,
- user-supplied code flag,
- network access,
- filesystem writes,
- external integration.

If risk exceeds threshold => `sandbox` mode.
If action explicitly disallowed => `deny` mode.
Else => `allow` mode.

## Execution policy handoff
1. Runtime submits `SandboxExecutionRequest`.
2. `SandboxPolicyEvaluator` returns `allow|sandbox|deny`.
3. `SandboxingDecisionEngine` emits decision audit event.
4. If `allow` or `sandbox`, engine hands off to `SandboxExecutor` with selected mode.
5. Engine emits execution audit event.

## Isolation expectations
In `sandbox` mode, execution should run in an isolated runtime boundary (e.g., future gVisor/container sandbox):
- constrained syscalls/process capabilities,
- bounded network egress,
- restricted filesystem writes,
- tighter resource quotas and observability.

## Deny vs sandbox decision
- `deny`: execution blocked immediately by policy.
- `sandbox`: execution allowed only in isolated mode.
- `allow`: execution may proceed without sandbox under low-risk conditions.

## Telemetry and audit implications
Audit events emitted:
- `sandbox.decision` with mode, reasons, risk score, policy reference.
- `sandbox.execute` for non-denied executions with selected mode.

These events should feed trust/security evidence pipelines for post-request review.
