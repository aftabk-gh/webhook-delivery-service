# ADR: Unique Constraint for Event Idempotency Keys

## Status
Accepted

## Problem
Idempotency must be enforced even if the application has a bug or two requests race.

It also has to be tenant-scoped. Two tenants may use the same `idempotency_key`, but one tenant must not duplicate its own key.

## Decision
Add a database unique constraint on:

```sql
(tenant_id, idempotency_key)
```

## Reasoning
This makes the database the final guard against duplicates.

The same key can be reused by different tenants safely, but a single tenant cannot create the same idempotent event twice.

## Alternatives Considered
**Unique idempotency key globally** — too strict. Different tenants could accidentally block each other.

**Application-only check** — not safe. It can fail during concurrent requests.

## Consequences
- Tenant isolation is preserved
- Duplicate event creation is blocked at the database level
- The `ON CONFLICT` insert has a clear conflict target
