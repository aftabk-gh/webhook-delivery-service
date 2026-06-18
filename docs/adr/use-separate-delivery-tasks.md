# ADR: Two-Task Delivery Architecture (deliver_event + deliver_to_endpoint)

## Problem

When an event arrives, it may match multiple active endpoints. You need to deliver
to all of them. The naive approach is one task that loops through every matching
endpoint and POSTs to each one sequentially.

That makes one slow endpoint delay every endpoint after it.

It also makes retries messy. If one endpoint fails and the whole task retries,
already-successful endpoints might be delivered again.

## Decision

Split into two tasks:

- `deliver_event` handles fan-out only. It finds matching endpoints, creates one
  delivery row per endpoint, and dispatches delivery tasks.
- `deliver_to_endpoint` handles one HTTP POST for one delivery.

Retries are scoped to one endpoint delivery, not the whole event.

## Alternatives and Tradeoffs

A single task would be simpler to follow, but one slow endpoint would block the
rest. Retrying that task would also risk duplicate sends to endpoints that already
succeeded.

Splitting the work creates more tasks and more moving parts. In return, each
delivery is isolated and can be retried independently.

## Consequences

- One bad endpoint does not delay other endpoints.
- Retry behavior is simpler and safer.
- The delivery queue can grow quickly for events with many matching endpoints.
- Observability must track both the fan-out task and individual delivery tasks.
