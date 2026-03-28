#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "error: git is required" >&2
  exit 1
fi

declare -A SUBMODULES=(
  ["ai-trust-security-stack"]="https://github.com/Amhdour/ai-trust-security-stack.git"
  ["overlays/myStarterKit"]="https://github.com/Amhdour/myStarterKit.git"
)

for path in "${!SUBMODULES[@]}"; do
  url="${SUBMODULES[$path]}"
  if git config -f .gitmodules --get "submodule.${path}.path" >/dev/null 2>&1; then
    echo "[skip] ${path} already exists in .gitmodules"
    continue
  fi

  echo "[add] ${path} -> ${url}"
  git submodule add "$url" "$path"
done

echo "Done. Run 'git submodule update --init --recursive' to populate the remaining managed submodule working trees."
