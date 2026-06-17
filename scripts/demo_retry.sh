#!/usr/bin/env bash
set -euo pipefail

# Usage: API_KEY="..." bash scripts/demo_retry.sh
# Requires: docker compose up -d already running

API="${API:-http://localhost:8000}"
RECEIVER="${RECEIVER:-http://localhost:9000}"
API_KEY="${API_KEY:?Set API_KEY from scripts/demo.sh output: API_KEY=... bash scripts/demo_retry.sh}"
RUN_ID="$(date +%Y%m%d%H%M%S)"
IDEMPOTENCY_KEY="${IDEMPOTENCY_KEY:-retry-${RUN_ID}}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command curl
require_command jq

echo "--- Setting receiver to always fail ---"
curl -fsS -X POST "${RECEIVER}/config" \
  -H "Content-Type: application/json" \
  -d '{"status_code":500}' | jq .

echo ""
echo "--- Sending event that should retry and exhaust ---"
EVENT="$(
  curl -fsS -X POST "${API}/events/" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    -d "{\"event_type\":\"order.created\",\"payload\":{\"order_id\":\"retry-${RUN_ID}\"},\"idempotency_key\":\"${IDEMPOTENCY_KEY}\"}"
)"
echo "${EVENT}" | jq .

EVENT_ID="$(echo "${EVENT}" | jq -er '.id')"

echo ""
echo "--- Watch retry lifecycle ---"
echo "docker compose logs celery-worker -f --since 0s 2>&1 | grep --line-buffered -o '{.*}' | jq --unbuffered ."
echo ""
echo "Trace this event:"
echo "docker compose logs celery-worker --since 20m 2>&1 | grep '${EVENT_ID}'"
echo ""
echo "Check delivery status:"
echo "curl -sS '${API}/deliveries/?status=exhausted' -H 'X-API-Key: ${API_KEY}' | jq ."
echo ""
echo "Reset receiver after the demo:"
echo "curl -sS -X POST '${RECEIVER}/config/reset' | jq ."
