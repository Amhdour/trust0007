#!/usr/bin/env bash
set -euo pipefail

TOKEN="${1:-}"
if [[ -z "$TOKEN" ]]; then
  echo "usage: $0 <jwt-token>" >&2
  exit 1
fi

PAYLOAD="$(echo "$TOKEN" | cut -d'.' -f2 | tr '_-' '/+' | base64 -d 2>/dev/null || true)"
if [[ -z "$PAYLOAD" ]]; then
  echo "error: failed to decode token payload" >&2
  exit 1
fi

echo "$PAYLOAD"
