#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

resolve_project_dir() {
  if [[ -d "$REPO_ROOT/trust" && -f "$REPO_ROOT/trust/Makefile" ]]; then
    printf '%s\n' "$REPO_ROOT/trust"
    return
  fi

  printf '%s\n' "$REPO_ROOT"
}

PROJECT_DIR="$(resolve_project_dir)"

cd "$REPO_ROOT"

echo "==> Preparing AI Trust & Security Readiness career project"
echo "==> Repo root: $REPO_ROOT"
echo "==> Project root: $PROJECT_DIR"

if [[ -f .gitmodules ]]; then
  git submodule update --init --recursive || true
fi

cd "$PROJECT_DIR"

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
echo "Run manually with: cd $PROJECT_DIR && make up-dev"
