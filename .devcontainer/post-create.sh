#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRUST_DIR="$REPO_ROOT/trust"

if [[ ! -d "$TRUST_DIR" ]]; then
  echo "ERROR: expected trust/ directory at $TRUST_DIR" >&2
  exit 1
fi

cd "$REPO_ROOT"

echo "==> Preparing AI Trust & Security Readiness career project"

if [[ -f .gitmodules ]]; then
  git submodule update --init --recursive || true
fi

cd "$TRUST_DIR"

python -m pip install --upgrade pip setuptools wheel

if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt
fi

if [[ -f pyproject.toml ]]; then
  pip install -e . || true
fi

chmod +x scripts/*.sh 2>/dev/null || true
chmod +x .devcontainer/*.sh 2>/dev/null || true

mkdir -p overlays/myStarterKit/artifacts
mkdir -p .devcontainer/.control-plane

echo "==> Project ready"
echo "Run manually with: make up-dev"
