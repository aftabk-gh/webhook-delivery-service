#!/usr/bin/env python
"""
Simple end-to-end load test. Run after demo.sh to have a tenant and endpoint set up.

Usage:
    API_KEY=your_key uv run python scripts/load_test.py

Optional overrides:
    API=http://localhost:8000 CONCURRENCY=20 TOTAL_EVENTS=200 DELIVERY_TIMEOUT=60
"""

import asyncio
import os
import time
from collections import Counter
from typing import Any

import httpx

API = os.environ.get("API", "http://localhost:8000")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "20"))
TOTAL_EVENTS = int(os.environ.get("TOTAL_EVENTS", "200"))
EVENT_TYPE = os.environ.get("EVENT_TYPE", "order.created")
DELIVERY_TIMEOUT = float(os.environ.get("DELIVERY_TIMEOUT", "60"))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "1"))
DELIVERY_PAGE_LIMIT = 100
TERMINAL_DELIVERY_STATUSES = {"success", "exhausted"}


async def send_event(client: httpx.AsyncClient, api_key: str, i: int) -> str | None:
    try:
        response = await client.post(
            f"{API}/events/",
            json={"event_type": EVENT_TYPE, "payload": {"i": i}},
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )
        if response.status_code not in (200, 202):
            return None
        return str(response.json()["id"])
    except httpx.HTTPError:
        return None


async def count_matching_endpoints(client: httpx.AsyncClient, api_key: str) -> int:
    response = await client.get(
        f"{API}/endpoints/",
        headers={"X-API-Key": api_key},
    )
    response.raise_for_status()

    endpoints: list[dict[str, Any]] = response.json()
    return sum(
        1
        for endpoint in endpoints
        if endpoint["is_active"] and EVENT_TYPE in endpoint["event_types"]
    )


async def fetch_delivery_status_counts(
    client: httpx.AsyncClient,
    api_key: str,
    event_ids: set[str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    cursor: str | None = None

    while True:
        params = {"limit": str(DELIVERY_PAGE_LIMIT)}
        if cursor is not None:
            params["cursor"] = cursor

        response = await client.get(
            f"{API}/deliveries/",
            params=params,
            headers={"X-API-Key": api_key},
        )
        response.raise_for_status()

        body = response.json()
        for delivery in body["items"]:
            if delivery["event_id"] in event_ids:
                counts[delivery["status"]] += 1

        cursor = body["next_cursor"]
        if cursor is None:
            return counts


async def wait_for_deliveries(
    client: httpx.AsyncClient,
    api_key: str,
    event_ids: set[str],
    expected_deliveries: int,
) -> tuple[Counter[str], float]:
    start = time.perf_counter()

    while True:
        counts = await fetch_delivery_status_counts(
            client=client,
            api_key=api_key,
            event_ids=event_ids,
        )
        terminal = sum(counts[status] for status in TERMINAL_DELIVERY_STATUSES)
        elapsed = time.perf_counter() - start

        if terminal >= expected_deliveries or elapsed >= DELIVERY_TIMEOUT:
            return counts, elapsed

        await asyncio.sleep(POLL_INTERVAL)


async def main() -> None:
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise RuntimeError(
            "API_KEY is required. Run: API_KEY=your_key uv run python scripts/load_test.py"
        )

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def bounded(client: httpx.AsyncClient, i: int) -> str | None:
        async with semaphore:
            return await send_event(client=client, api_key=api_key, i=i)

    async with httpx.AsyncClient(timeout=10) as client:
        matching_endpoint_count = await count_matching_endpoints(
            client=client,
            api_key=api_key,
        )

        start = time.perf_counter()
        results = await asyncio.gather(
            *[bounded(client=client, i=i) for i in range(TOTAL_EVENTS)]
        )
        ingestion_elapsed = time.perf_counter() - start

        event_ids = {event_id for event_id in results if event_id is not None}
        success = len(event_ids)
        failed = TOTAL_EVENTS - success
        ingestion_throughput = TOTAL_EVENTS / ingestion_elapsed
        expected_deliveries = success * matching_endpoint_count

        print(f"Sent {TOTAL_EVENTS} events in {ingestion_elapsed:.2f}s")
        print(f"Accepted: {success} | Failed: {failed}")
        print(f"Ingestion throughput: {ingestion_throughput:.1f} events/sec")
        print(f"Matching endpoints: {matching_endpoint_count}")

        if expected_deliveries == 0:
            print("Expected deliveries: 0")
            return

        delivery_counts, delivery_elapsed = await wait_for_deliveries(
            client=client,
            api_key=api_key,
            event_ids=event_ids,
            expected_deliveries=expected_deliveries,
        )

    terminal_deliveries = sum(
        delivery_counts[status] for status in TERMINAL_DELIVERY_STATUSES
    )
    delivery_throughput = (
        terminal_deliveries / delivery_elapsed if delivery_elapsed else 0
    )
    status_summary = ", ".join(
        f"{status}={count}" for status, count in sorted(delivery_counts.items())
    )
    print(f"Expected deliveries: {expected_deliveries}")
    print(
        "Completed deliveries: "
        f"{terminal_deliveries} in {delivery_elapsed:.2f}s "
        f"({delivery_throughput:.1f} deliveries/sec)"
    )
    print(f"Delivery statuses: {status_summary or 'none'}")

    if terminal_deliveries < expected_deliveries:
        print(f"Timed out waiting for deliveries after {DELIVERY_TIMEOUT:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
