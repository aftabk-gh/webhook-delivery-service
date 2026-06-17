#!/usr/bin/env bash
set -euo pipefail

# Usage: bash scripts/demo.sh
# Requires: docker compose up -d already running

API="${API:-http://localhost:8000}"
RECEIVER_PUBLIC="${RECEIVER_PUBLIC:-http://localhost:9000}"
RECEIVER_INTERNAL="${RECEIVER_INTERNAL:-http://test-receiver:9000}"
RUN_ID="$(date +%Y%m%d%H%M%S)"
IDEMPOTENCY_KEY="${IDEMPOTENCY_KEY:-demo-${RUN_ID}}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command curl
require_command jq

echo "--- Creating tenant ---"
TENANT="$(
  curl -fsS -X POST "${API}/tenants/" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"demo-tenant-${RUN_ID}\"}"
)"
echo "${TENANT}" | jq .

API_KEY="$(echo "${TENANT}" | jq -er '.api_key')"

echo ""
echo "--- Creating endpoint ---"
ENDPOINT="$(
  curl -fsS -X POST "${API}/endpoints/" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    -d "{\"url\":\"${RECEIVER_INTERNAL}/webhook\",\"event_types\":[\"order.created\"]}"
)"
echo "${ENDPOINT}" | jq .

echo ""
echo "--- Sending event ---"
EVENT="$(
  curl -fsS -X POST "${API}/events/" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    -d "{\"event_type\":\"order.created\",\"payload\":{\"order_id\":\"${RUN_ID}\",\"amount\":99.99},\"idempotency_key\":\"${IDEMPOTENCY_KEY}\"}"
)"
echo "${EVENT}" | jq .

EVENT_ID="$(echo "${EVENT}" | jq -er '.id')"

echo ""
echo "--- Sending duplicate event ---"
DUPLICATE_EVENT="$(
  curl -fsS -X POST "${API}/events/" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    -d "{\"event_type\":\"order.created\",\"payload\":{\"order_id\":\"${RUN_ID}\",\"amount\":99.99},\"idempotency_key\":\"${IDEMPOTENCY_KEY}\"}"
)"
echo "${DUPLICATE_EVENT}" | jq .

echo ""
echo "--- Done ---"
echo "API_KEY=${API_KEY}"
echo "EVENT_ID=${EVENT_ID}"
echo ""
echo "Celery lifecycle:"
echo "docker compose logs celery-worker --since 10m 2>&1 | grep '${EVENT_ID}'"
echo ""
echo "Structured Celery logs:"
echo "docker compose logs celery-worker -f --since 0s 2>&1 | grep --line-buffered -o '{.*}' | jq --unbuffered ."
echo ""
echo "Test receiver dashboard:"
echo "${RECEIVER_PUBLIC}"
echo ""
echo "Delivery logs API:"
echo "curl -sS '${API}/deliveries/' -H 'X-API-Key: ${API_KEY}' | jq ."
echo ""
echo "Retry demo:"
echo "API_KEY='${API_KEY}' bash scripts/demo_retry.sh"
