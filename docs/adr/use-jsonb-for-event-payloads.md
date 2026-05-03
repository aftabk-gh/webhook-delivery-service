# ADR: JSONB over JSON for Event Payloads

## Status
Accepted

## Problem
Event payloads need to be stored in PostgreSQL. Two options exist: `JSON` and `JSONB`.
The choice affects query performance, indexing capability, and scalability.

## Decision
Use `JSONB` for storing event payloads.

## Reasoning

### How they differ

`JSON` stores the raw text as-is. Every time you query into it, Postgres re-parses the string.

`JSONB` stores data in a decomposed binary format. Parsing happens once on insert. Reads are faster and the column can be indexed.

### Practical difference

```sql
-- JSON: no index possible, full table scan every time
SELECT payload->>'user_id' FROM events
WHERE payload->>'user_id' = '123';

-- JSONB: index the column, use containment operator
CREATE INDEX idx_events_payload ON events USING GIN (payload);

SELECT payload->>'user_id' FROM events
WHERE payload @> '{"user_id": 123}';
-- Hits the index
```

The `@>` containment operator only works on `JSONB`.

### Tradeoffs

| | JSON | JSONB |
|---|---|---|
| Write speed | Faster (stores raw text) | Slightly slower (parses on insert) |
| Read speed | Slower (parses on every read) | Faster (binary, parsed once) |
| Indexing | Not possible | GIN index supported |
| Operators | Basic | Includes `@>`, `?`, `?&` |
| Key ordering | Preserved | Not preserved |

## Alternatives Considered

**Plain JSON** — simpler writes, but no indexing. Becomes a bottleneck at scale when filtering or searching payloads.

## Consequences

- Payload queries can be indexed and run in milliseconds at scale
- Slightly higher insert cost — acceptable given read-heavy delivery log queries
- Key ordering in payload is not guaranteed — not a concern for this use case

## Validation

Run `EXPLAIN ANALYZE` on a payload query with 10k+ rows to confirm index scan vs sequential scan.
