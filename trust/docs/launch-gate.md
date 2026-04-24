# Launch Gate Layer

## Scope
Evidence-based launch decision layer for local development integration.

## Decision outputs
The gate returns one of:
- `pass`
- `conditional_go`
- `no_go`

## Inputs
- Evidence artifact map (`event_type` or control evidence keys => boolean present/absent)
- Required control definitions (mandatory/optional + evidence requirements + scoring weights)
- Kill-switch flag

## Requirements handled
- Consume evidence artifacts.
- Evaluate required controls.
- Support pass / conditional_go / no_go.
- Expose blockers.
- Expose missing evidence.
- Support kill-switch concept.
- Generate machine-readable and human-readable outputs.

## Scoring model (explicit)
- Each control has an explicit integer weight.
- `score` is sum of passed control weights.
- `max_score` is sum of all control weights.

## Decision logic
1. If kill switch is enabled => `no_go`.
2. Mandatory controls missing evidence => `no_go` blockers.
3. Any missing evidence (non-mandatory only) with no blockers => `conditional_go`.
4. `pass` only when all required evidence is present and score == max_score.
5. No green without evidence.

## Output formats
- Machine-readable JSON object (decision, score, blockers, missing evidence, control status).
- Human-readable summary text.

## Integration notes
- Launch gate should ingest telemetry/audit artifacts from `telemetry/exports/`.
- In future CI/CD integration, `no_go` should block rollout; `conditional_go` can require explicit approval.
