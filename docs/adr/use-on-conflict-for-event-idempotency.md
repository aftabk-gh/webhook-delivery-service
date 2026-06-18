# ADR: ON CONFLICT for Event Idempotency

## Problem

Two identical event requests can arrive at the same time.

If the application checks for an existing event and then inserts a new one, both
requests can race. They can both see that no event exists yet, then both try to
create one.

That would create duplicate events and duplicate deliveries.

## Decision

Use PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` for event idempotency.

The database is the safest place to decide which request wins during a race.

One request inserts the event. The duplicate request hits the conflict and gets
the existing event instead of creating a second one.

## Alternatives and Tradeoffs

The main alternative is `SELECT` then `INSERT`. That is easier to read at first,
but it is unsafe under concurrency unless extra locking is added.

Using `ON CONFLICT` pushes the race handling into PostgreSQL. The tradeoff is
that the code is a little more database-specific, and it requires a clear unique
constraint.

## Consequences

- Concurrent duplicate requests do not create duplicate events.
- Duplicate idempotency keys return the existing event.
- Celery dispatch only happens for the request that creates the event.
- The behavior depends on a database unique constraint.
