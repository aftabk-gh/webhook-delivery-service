# ADR: ON CONFLICT for Event Idempotency

## Status
Accepted

## Problem
Two identical event requests can arrive at the same time.

If the code first checks for an existing event and then inserts a new one, both requests can see "nothing exists yet" and both try to create the event.

## Decision
Use PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` for event idempotency.

## Reasoning
The database is the only place that can safely decide the winner when two requests race.

One request inserts the event. The other request hits the conflict and gets the existing event ID instead of creating a duplicate.

This keeps the API behavior simple:

- new `idempotency_key` -> create event and dispatch Celery task
- repeated `idempotency_key` -> return original event ID and do not dispatch again

## Alternatives Considered
**SELECT then INSERT** — easier to read, but unsafe under concurrency.

## Consequences
- Prevents duplicate events during concurrent requests
- Prevents duplicate Celery dispatch for the same event creation request
- Requires a database unique constraint to define what counts as a duplicate
