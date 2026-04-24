#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$#" -gt 0 ]]; then
  ENV_FILES=("$@")
else
  ENV_FILES=("$ROOT_DIR/compose/.env.production" "$ROOT_DIR/.env.live")
fi

printf '\n==> Verifying live environment configuration\n'
bash "$ROOT_DIR/scripts/verify-live-env.sh" "${ENV_FILES[@]}"

printf '\n==> Verifying remote Onyx connectivity\n'
bash "$ROOT_DIR/scripts/verify-remote-onyx.sh" "${ENV_FILES[@]}"

printf '\n==> Preflight complete\n'
printf 'Onyx (runtime) + Trust (governance/readiness) integration checks passed for:'
for env_file in "${ENV_FILES[@]}"; do
  printf ' %s' "$env_file"
done
printf '\n'
