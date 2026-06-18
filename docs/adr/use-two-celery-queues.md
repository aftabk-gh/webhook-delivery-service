# ADR: Two Celery Queues (default and delivery)

## Problem

Both tasks could run on a single shared queue. The issue is they have completely
different characteristics.

`deliver_event` is fast. It does a DB read, creates some records, dispatches tasks.
No network calls, no waiting.

`deliver_to_endpoint` is slow. It makes an outbound HTTP POST to an external server
that may be slow, overloaded, or timing out after 10 seconds.

On a shared queue, a backlog of slow delivery tasks builds up and blocks fan-out
tasks sitting behind them. New events stop being processed even though the actual
bottleneck is outbound HTTP — not ingestion. The two workloads are interfering with
each other for no reason.

## Decision

Use two Celery queues:

- `default` for fan-out tasks.
- `delivery` for outbound HTTP delivery tasks.

This keeps fast fan-out work separate from slower network delivery work.

## Alternatives and Tradeoffs

A single queue would be simpler to configure. It would also make slow delivery
tasks compete with fan-out tasks.

Two queues require more worker configuration. In return, delivery workers can be
scaled independently, and a delivery backlog does not stop fan-out.

## Consequences

- Event fan-out can keep moving even when outbound delivery is slow.
- More workers can be assigned to the `delivery` queue when needed.
- Celery configuration is slightly more complex.
- Queue names become part of the operational model.
