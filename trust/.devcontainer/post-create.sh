#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

git submodule update --init --recursive || true

python -m pip install --upgrade pip setuptools wheel

if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt
fi

if [[ -f pyproject.toml ]]; then
  pip install -e . || true
fi

mkdir -p overlays/myStarterKit/artifacts
mkdir -p .devcontainer/.control-plane

chmod +x scripts/*.sh 2>/dev/null || true
