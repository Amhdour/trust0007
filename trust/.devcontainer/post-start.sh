#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BOOT_MODE="${TRUST_CODESPACE_BOOT_MODE:-local}"

if [[ "$BOOT_MODE" == "none" ]]; then
  echo "Auto-start disabled. Run: make up-dev"
  exit 0
fi

if [[ "$BOOT_MODE" == "compose" || "$BOOT_MODE" == "live" ]]; then
  make up-dev
  exit 0
fi

bash scripts/start-control-plane.sh
