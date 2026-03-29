from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

QUESTION_PREVIEW_LIMIT = 120
GOVERNED_REQUEST_FEED_LIMIT = 12

_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str], str | Any], ...] = (
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE | re.DOTALL),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._=-]{8,}\b"),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b"),
        "[REDACTED_JWT]",
    ),
    (
        "api_key_label",
        re.compile(r"(?i)\b(api[_ -]?key|token|secret|password|passwd|authorization)\b\s*([:=])\s*([^\s,;]+)"),
        lambda match: f"{match.group(1)}{match.group(2)} [REDACTED_VALUE]",
    ),
    (
        "openai_key",
        re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
        "[REDACTED_API_KEY]",
    ),
    (
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        "[REDACTED_TOKEN]",
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "[REDACTED_TOKEN]",
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_ACCESS_KEY]",
    ),
    (
        "url_credentials",
        re.compile(r"(?i)\bhttps?://([^/\s:@]+):([^@\s/]+)@"),
        lambda match: f"https://{match.group(1)}:[REDACTED]@",
    ),
    (
        "opaque_secret",
        re.compile(r"\b(?=[A-Za-z0-9_+=-]{24,}\b)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_+=-]{24,}\b"),
        "[REDACTED_SECRET]",
    ),
)


def _normalize_question(prompt: str) -> str:
    collapsed = " ".join(str(prompt or "").split())
    return collapsed or "[empty governed request]"


def _truncate_preview(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return f"{text[: max(0, limit - 1)].rstrip()}...", True


def sanitize_question(prompt: str, *, preview_limit: int = QUESTION_PREVIEW_LIMIT) -> dict[str, Any]:
    normalized = _normalize_question(prompt)
    sanitized = normalized
    detected_patterns: list[str] = []

    for label, pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized, count = pattern.subn(replacement, sanitized)
        if count:
            detected_patterns.append(label)

    preview, truncated = _truncate_preview(sanitized, preview_limit)
    return {
        "question_preview": preview,
        "question_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "question_redacted": sanitized != normalized,
        "question_truncated": truncated,
        "contains_sensitive_patterns": bool(detected_patterns),
        "sensitive_pattern_labels": detected_patterns,
        "question_length": len(normalized),
    }


def append_governed_request_feed(path: Path, record: dict[str, Any], *, limit: int = GOVERNED_REQUEST_FEED_LIMIT) -> list[dict[str, Any]]:
    existing: list[dict[str, Any]] = []
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            existing = [item for item in payload if isinstance(item, dict)]

    updated = [record]
    updated.extend(
        item
        for item in existing
        if str(item.get("trace_id", "")) != str(record.get("trace_id", ""))
    )
    updated.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    trimmed = updated[:limit]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trimmed, indent=2, sort_keys=True), encoding="utf-8")
    return trimmed


def write_history_artifacts(history_root: Path, trace_id: str, payloads: dict[str, dict[str, Any]]) -> dict[str, str]:
    history_dir = history_root / trace_id
    history_dir.mkdir(parents=True, exist_ok=True)

    refs: dict[str, str] = {}
    for name, payload in payloads.items():
        path = history_dir / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        refs[name.replace("-", "_")] = str(path)
    return refs
