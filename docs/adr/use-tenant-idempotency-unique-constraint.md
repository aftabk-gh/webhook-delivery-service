# ADR: Unique Constraint for Event Idempotency Keys

## Problem

Idempotency must be enforced even if the application has a bug or two requests race.

It also has to be tenant-scoped. Two tenants may use the same `idempotency_key`,
but one tenant must not create two events with the same key.

## Decision

Add a database unique constraint on:

```sql
(tenant_id, idempotency_key)
```

This makes the database the final guard against duplicates.

The same key can be reused by different tenants safely, but a single tenant cannot create the same idempotent event twice.

## Alternatives and Tradeoffs

A globally unique `idempotency_key` would be simpler, but it would be wrong for a
multi-tenant system. Different tenants could accidentally block each other by
using the same key.

An application-only check would avoid a database constraint, but it would not be
safe during concurrent requests.

The tenant-scoped unique constraint is slightly more specific, but it matches the
real business rule.

## Consequences

- Tenant isolation is preserved.
- Duplicate event creation is blocked at the database level.
- The same idempotency key can be reused by different tenants.
- `INSERT ... ON CONFLICT` has a clear conflict target.
