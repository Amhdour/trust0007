"""Shared telemetry constants used across modeling and export layers."""

REQUIRED_EVENT_TYPES = [
    "request.start",
    "request.question_received",
    "request.question_sanitized",
    "request.question_classified",
    "identity.established",
    "identity.session",
    "policy.decision",
    "policy.input",
    "retrieval.decision",
    "retrieval.execution",
    "tool.decision",
    "tool.execution_attempt",
    "secret.access",
    "confirmation.required",
    "deny.event",
    "fallback.event",
    "trace.correlation",
    "launch_gate.evaluated",
    "handoff.decision",
    "request.end",
    "incident.signal",
]

# Common secret-like keys to redact at telemetry creation time.
SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "authorization"}

# Internal audit-heavy events usually excluded from external observability export by default.
INTERNAL_ONLY_EVENT_TYPES = {"deny.event", "incident.signal"}
