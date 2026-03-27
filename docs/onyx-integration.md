# Onyx Gateway Adapter Integration (myStarterKit Controls)

## Purpose
`adapters/onyx_gateway_adapter/` provides a boundary adapter that accepts normalized runtime requests and applies governance checks without depending on upstream Onyx internals.

## Responsibilities implemented
- Accept normalized request input from runtime (`NormalizedRequest`).
- Invoke policy checks (`PolicyChecker`).
- Invoke retrieval checks (`RetrievalChecker`).
- Invoke tool decision checks (`ToolDecisionChecker`).
- Emit telemetry events (`TelemetryEmitter`).
- Return normalized decision output (`NormalizedDecision`).

## Interfaces
- `PolicyChecker.check_policy(request) -> PolicyDecision`
- `RetrievalChecker.check_retrieval(request) -> RetrievalDecision`
- `ToolDecisionChecker.check_tools(request) -> ToolDecision`
- `TelemetryEmitter.emit(event) -> None`

These interfaces are intentionally minimal and stable for local-development integration.

## Typed schemas
Defined dataclass schemas:
- `NormalizedRequest`
- `PolicyDecision`
- `RetrievalDecision`
- `ToolDecision`
- `TelemetryEvent`
- `NormalizedDecision`

## Decision semantics
The adapter returns `allow=true` only when:
1. policy check allows,
2. retrieval check allows,
3. no tools are denied.

Any failed check results in deny with aggregated reasons.

## Independence from upstream Onyx internals
- Adapter only consumes normalized DTOs and interfaces.
- No import or coupling to upstream `upstream/onyx` modules.
- Integration point can be attached by a thin runtime wrapper.

## Test coverage
`tests/adapter/test_onyx_gateway_adapter.py` includes:
- happy path allow scenario,
- deny path scenario,
- telemetry emission assertions.
