# ADR: SELECT FOR UPDATE SKIP LOCKED for Delivery Processing

## Status
Accepted

## The Problem

Multiple Celery workers run at the same time and pull from the same delivery queue.
Two workers can pick up the same `deliver_to_endpoint` task simultaneously and both
try to process the same delivery row.

Without any protection, both workers make the HTTP POST to the external endpoint.
The receiver gets the same webhook twice. No error is thrown. No log tells you this
happened. Silent duplicate.

## What Happens Without SKIP LOCKED

If you use `SELECT FOR UPDATE` alone:

- Worker 1 locks the row and starts processing
- Worker 2 hits the same row and blocks — it just waits
- Worker 1 finishes, commits, releases the lock
- Worker 2 now acquires the lock and processes the same row again
- Duplicate HTTP POST

The lock alone does not prevent duplicates. It just serialises them.

## The Fix

Add `SKIP LOCKED` to the select:

- Worker 1 locks the row
- Worker 2 sees the row is locked, skips it, gets nothing back, exits cleanly
- One delivery. The second worker is a no-op.

The `status = 'pending'` filter in the query does the rest. Once Worker 1 commits
and sets status to `success`, no future worker will ever pick that row up again
regardless of locking — because pending is gone.

## One Line

Lock the row or skip it entirely — never wait.
