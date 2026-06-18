# ADR: SELECT FOR UPDATE SKIP LOCKED for Delivery Processing

## Problem

Multiple Celery workers run at the same time and pull from the same delivery queue.
Two workers can pick up the same `deliver_to_endpoint` task simultaneously and both
try to process the same delivery row.

Without any protection, both workers make the HTTP POST to the external endpoint.
The receiver gets the same webhook twice.

## Decision

Use `SELECT FOR UPDATE SKIP LOCKED` when a worker claims a pending delivery row.

The first worker locks the row and processes it. A second worker trying to claim
the same row skips it and exits cleanly.

## Alternatives and Tradeoffs

`SELECT FOR UPDATE` without `SKIP LOCKED` would make the second worker wait. After
the first worker commits, the second worker could continue and process stale work.
That can still lead to duplicate delivery.

Application-level checks are not enough because the race happens between workers.
The database row lock is the shared truth both workers must respect.

`SKIP LOCKED` makes the second worker a no-op instead of a duplicate sender. The
tradeoff is that workers need to treat "no row returned" as a normal outcome.

## Consequences

- Only one worker can claim a delivery row.
- Duplicate task pickup becomes safe.
- Workers must handle skipped rows without treating them as errors.
- The delivery query must stay in the raw SQL data layer because this is
  concurrency-critical.
