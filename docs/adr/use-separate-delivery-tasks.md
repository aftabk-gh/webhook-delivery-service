# ADR: Two-Task Delivery Architecture (deliver_event + deliver_to_endpoint)

## Status
Accepted

## The Problem

When an event arrives, it may match multiple active endpoints. You need to deliver
to all of them. The naive approach is one task that loops through every matching
endpoint and POSTs to each one sequentially.

This breaks in two ways.

## What Breaks With a Single Task

**One slow endpoint blocks everyone.**
If endpoint 3 takes 10 seconds to respond (or times out), endpoints 4 through 10
wait behind it. A single unresponsive endpoint adds minutes of delay to deliveries
that have nothing to do with it.

**Retry logic becomes a mess.**
If endpoint 3 fails and you retry the whole task, you re-run the fan-out. Endpoints
1 and 2 already succeeded — now you're delivering to them again. You either accept
duplicates or build complex "skip already delivered" logic inside the task. Neither
is good.

## The Fix

Split into two tasks:

`deliver_event` — fan-out only. Finds all matching endpoints, creates one Delivery
record per endpoint, dispatches one `deliver_to_endpoint` task per endpoint. Done.

`deliver_to_endpoint` — one HTTP POST. Handles exactly one delivery. Retries are
scoped to this one endpoint only. A failure here affects nothing else.

## Why Two Queues

`deliver_event` goes on the `default` queue. `deliver_to_endpoint` goes on the
`delivery` queue. This lets you scale them independently — more delivery workers
during high load, without touching the fan-out workers. It also gives you a clean
place to apply different concurrency and rate settings to each workload.

## One Line

Fan-out once, deliver independently — so one bad endpoint never becomes everyone's problem.
