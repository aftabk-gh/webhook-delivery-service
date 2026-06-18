# Known Gaps

This project is intentionally small enough to understand end to end.

The core system is built: events come in, deliveries are created, workers send
webhooks, failures retry, and stuck work can be recovered.

The gaps below are things a production system would need next. They were skipped
on purpose so the first version stays focused.

## Circuit Breaker

Right now, if an endpoint is down, the system retries a few times and then marks
that delivery as exhausted.

The gap is that future events will still try that same endpoint again.

A circuit breaker would notice that an endpoint keeps failing and temporarily
stop sending new deliveries to it. After a short cooldown, it would send one test
delivery to see if the endpoint has recovered.

This protects worker capacity and avoids wasting time on endpoints that are
clearly unhealthy.

## Rate Limiting

Right now, a tenant can send as many events as they want.

The gap is that one busy tenant could flood the system and slow down everyone
else.

Rate limiting would put a clear limit on how many events a tenant can send in a
time window. If they go over the limit, the API would return `429 Too Many
Requests` and tell them when to try again.

This protects the service from accidental spikes and noisy tenants.

## Per-Tenant Worker Isolation

Right now, all tenants share the same Celery queues.

The gap is that a large backlog from one tenant can sit in the same queue as work
from another tenant.

A production version could route tenants to separate queues, or give higher-tier
tenants their own worker pool.

This makes delivery time more predictable when one tenant has a burst of traffic.

## API Key Hashing

Right now, API keys are stored directly in the database.

The gap is that if the database were leaked, the keys would be exposed.

A production version should store only a hash of each API key. When a request
comes in, the service would hash the provided key and compare hashes.

This is the same basic idea as password storage: keep secrets useful for
verification, but do not store the raw secret.

## Payload Encryption At Rest

Right now, event payloads are stored as plain `JSONB`.

The gap is that sensitive payload data is readable by anyone with database
access.

A production version could encrypt sensitive payload fields, or encrypt the full
payload before storing it.

This matters when webhook payloads contain private customer data.

## Prometheus Metrics

Right now, the project relies mostly on logs and database state to understand
what happened.

The gap is that there is no `/metrics` endpoint for dashboards and alerts.

A production version should expose counters and histograms for things like:

- events received
- deliveries attempted
- deliveries succeeded
- deliveries failed
- retry count
- delivery latency
- queue depth

This makes it easier to see system health without reading logs manually.

## Transactional Outbox

Right now, the API writes the event to Postgres and then sends a Celery task.

The gap is that those are two separate writes. If the API crashes after the
database commit but before the Celery task is sent, the event exists but may not
be delivered.

A production version should use the transactional outbox pattern. That means the
API writes both the event and an "outbox message" in the same database
transaction. A separate worker then publishes outbox messages to Celery.

This closes the small reliability gap between database writes and queue
publishing.

## Final Note

These gaps do not mean the project is unfinished. They show the boundary between
a solid learning version and a full production platform.

The important part is knowing what was skipped, why it was skipped, and what the
next version would add.
