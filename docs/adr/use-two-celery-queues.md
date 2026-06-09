# ADR: Two Celery Queues (default and delivery)

## Status
Accepted

## The Problem

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

## The Fix

Two queues. `default` for fan-out, `delivery` for HTTP delivery.

This means a delivery backlog never touches fan-out. Event ingestion keeps moving
regardless of how many slow endpoints are piling up on the delivery side.

It also lets you scale them independently. If delivery is the bottleneck, point more
workers at the `delivery` queue. The `default` queue stays unaffected.

## One Line

Different workloads need different queues — so a slow external endpoint never backs
up event ingestion.
