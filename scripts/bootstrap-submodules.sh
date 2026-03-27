#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "error: git is required" >&2
  exit 1
fi

declare -A SUBMODULES=(
  ["upstream/onyx"]="https://github.com/onyx-dot-app/onyx.git"
  ["upstream/keycloak"]="https://github.com/keycloak/keycloak.git"
  ["upstream/keycloak-quickstarts"]="https://github.com/keycloak/keycloak-quickstarts.git"
  ["upstream/envoy"]="https://github.com/envoyproxy/envoy.git"
  ["upstream/opa"]="https://github.com/open-policy-agent/opa.git"
  ["upstream/opa-envoy-plugin"]="https://github.com/open-policy-agent/opa-envoy-plugin.git"
  ["upstream/vault"]="https://github.com/hashicorp/vault.git"
  ["upstream/qdrant"]="https://github.com/qdrant/qdrant.git"
  ["upstream/gvisor"]="https://github.com/google/gvisor.git"
  ["upstream/langfuse"]="https://github.com/langfuse/langfuse.git"
  ["upstream/langfuse-python"]="https://github.com/langfuse/langfuse-python.git"
  ["upstream/grafana"]="https://github.com/grafana/grafana.git"
  ["upstream/superset"]="https://github.com/apache/superset.git"
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

echo "Done. Run 'git submodule update --init --recursive' to populate submodule working trees."
