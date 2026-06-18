# ADR: JSONB over JSON for Event Payloads

## Problem

Webhook event payloads need to be stored in PostgreSQL.

The simple option is `JSON`. The more query-friendly option is `JSONB`.

This matters because delivery logs and future debugging tools may need to inspect
payload fields. If the payload column cannot be indexed well, those queries get
slow as the table grows.

## Decision

Use `JSONB` for storing event payloads.

## Alternatives and Tradeoffs

`JSON` would store the raw payload text with slightly cheaper writes. That is
simple, but it gives fewer useful query and indexing options.

`JSONB` parses the payload on write and stores it in a binary form. Writes can be
slightly more expensive, and key order is not preserved. In return, reads are
faster and PostgreSQL can use JSONB indexes and operators.

For this service, queryability matters more than preserving raw key order.

## Consequences

- Payload fields can be queried more efficiently.
- Future payload search or filtering can use JSONB indexes.
- Inserts may cost slightly more CPU.
- Payload key order is not guaranteed.
