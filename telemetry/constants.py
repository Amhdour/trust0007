"""Shared telemetry constants used across modeling and export layers."""

REQUIRED_EVENT_TYPES = [
    "request.start",
    "identity.established",
    "policy.decision",
    "retrieval.decision",
    "tool.decision",
    "tool.execution_attempt",
    "confirmation.required",
    "deny.event",
    "fallback.event",
    "request.end",
    "incident.signal",
]

# Common secret-like keys to redact at telemetry creation time.
SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "authorization"}

# Internal audit-heavy events usually excluded from external observability export by default.
INTERNAL_ONLY_EVENT_TYPES = {"deny.event", "incident.signal"}
