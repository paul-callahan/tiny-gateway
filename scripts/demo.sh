#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/demo.sh [--down]

Options:
  --down    Stop the compose stack before exiting.

Environment:
  TINY_GATEWAY_CONFIG_FILE  Path to config YAML mounted into compose stack.
                            Defaults to ./sample-configs/basic-single-tenant.yml
  TINY_GATEWAY_PORT         Host port for Tiny Gateway (default: 8000)
EOF
}

AUTO_DOWN=0
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--down" ]]; then
  AUTO_DOWN=1
fi

CONFIG_FILE="${TINY_GATEWAY_CONFIG_FILE:-${REPO_ROOT}/sample-configs/basic-single-tenant.yml}"
if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Config file not found: ${CONFIG_FILE}" >&2
  exit 1
fi

export TINY_GATEWAY_CONFIG_FILE="${CONFIG_FILE}"
PORT="${TINY_GATEWAY_PORT:-8000}"
BASE_URL="http://localhost:${PORT}"

if [[ "${AUTO_DOWN}" -eq 1 ]]; then
  trap 'docker compose down >/dev/null 2>&1 || true' EXIT
fi

echo "Starting Tiny Gateway demo stack with config: ${TINY_GATEWAY_CONFIG_FILE}"
docker compose up -d

echo "Waiting for health endpoint..."
for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/health" >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl -fsS "${BASE_URL}/health" >/dev/null; then
  echo "Tiny Gateway did not become healthy in time. Recent logs:" >&2
  docker compose logs --tail 80 tiny-gateway >&2 || true
  exit 1
fi

echo "Requesting token..."
LOGIN_JSON="$(curl -fsS -X POST "${BASE_URL}/api/v1/auth/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=admin123')"

TOKEN="$(printf '%s' "${LOGIN_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

echo "Calling proxied route /api/service ..."
PROXY_JSON="$(curl -fsS "${BASE_URL}/api/service" -H "Authorization: Bearer ${TOKEN}")"

echo
echo "Health response:"
curl -fsS "${BASE_URL}/health"
echo
echo "Proxy response:"
echo "${PROXY_JSON}"
echo
echo "Demo complete."

if [[ "${AUTO_DOWN}" -eq 0 ]]; then
  echo "Stack is still running. Stop with: docker compose down"
fi

