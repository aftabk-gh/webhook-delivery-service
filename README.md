# webhook-delivery-service

Production-grade webhook delivery infrastructure for multi-tenant event ingestion,
reliable HTTP delivery, retries, HMAC signing, and crash recovery.

Stack: FastAPI, PostgreSQL, Redis, Celery, and Docker Compose.

## Links

- [Architecture](#architecture)
- [Local Setup](#local-setup)
- [Architecture Decisions](docs/adr/)
- [Known Gaps](docs/known-gaps.md)

## Architecture

```mermaid
graph TB
    %% ============================================================
    %% Webhook Delivery Service — runtime data flow (top-down)
    %% Solid edges  = task / message / request flow
    %% Dashed edges = Postgres reads & writes (source of truth)
    %% ============================================================

    %% ---- Styles ----
    classDef storage fill:#f9f,stroke:#333,stroke-width:2px;
    classDef compute fill:#bbf,stroke:#333,stroke-width:2px;
    classDef external fill:#eee,stroke:#333,stroke-width:2px;
    classDef queue fill:#ffd9a8,stroke:#333,stroke-width:1px;

    %% ---- External actors ----
    Client((Client)):::external

    %% ---- Synchronous ingestion ----
    subgraph Sync [Synchronous Ingestion]
        direction TB
        API[Ingestion API<br/><i>FastAPI</i>]:::compute
    end

    %% ---- Async processing via Celery / Redis ----
    %% Beat lives inside this subgraph so its re-enqueue edge stays local
    %% to the queues and does not cross the fan-out spine.
    %% Target sits at the bottom of the spine so the HTTP edge runs straight
    %% down (inside the box) and does not run parallel to the dashed DB edge.
    subgraph Async [Asynchronous Processing — Celery]
        direction TB
        QDefault{{Redis: default queue}}:::queue
        FanOut[deliver_event<br/><i>fan-out task</i>]:::compute
        QDelivery{{Redis: delivery queue}}:::queue
        Deliver[deliver_to_endpoint<br/><i>delivery task</i>]:::compute
        Beat[Recovery Scheduler<br/><i>Celery Beat — every 5m</i>]:::compute
        Target((External<br/>Endpoint)):::external
    end

    %% ---- Source of truth (placed last so it sinks to the bottom) ----
    DB[(Event Store<br/><i>Postgres</i><br/>events · deliveries)]:::storage

    %% ===== Primary flow (solid) — the vertical spine =====
    Client -- "POST /events/<br/>(X-API-Key)" --> API
    API == "enqueue" ==> QDefault
    QDefault == "consume" ==> FanOut
    FanOut == "fan-out:<br/>1 task / endpoint" ==> QDelivery
    QDelivery == "consume" ==> Deliver
    Deliver -- "HTTP POST + HMAC-SHA256<br/>(10s timeout)" --> Target

    %% Synchronous 202 response (short, kept near the API)
    API -. "202 Accepted<br/>(no wait)" .-> Client

    %% Retry loop on the delivery task
    Deliver -- "retry: backoff<br/>30s / 2m / 10m,<br/>then exhausted" --> Deliver

    %% ===== Recovery re-enqueue (solid) — declared near its source =====
    Beat == "re-enqueue<br/>stuck deliveries" ==> QDelivery

    %% ===== Postgres reads & writes (dashed), labels wrapped =====
    API -. "INSERT ON CONFLICT<br/>DO NOTHING<br/>(idempotency)" .-> DB
    FanOut -. "read event +<br/>matching endpoints;<br/>INSERT pending deliveries" .-> DB
    Deliver -. "SELECT FOR UPDATE<br/>SKIP LOCKED;<br/>UPDATE status" .-> DB
    Beat -. "scan pending where<br/>next_retry_at < now" .-> DB

    %% ---- Link styling ----
    %% Edge index order (in declaration order above):
    %% 0  Client-->API                solid
    %% 1  API==>QDefault              thick
    %% 2  QDefault==>FanOut           thick
    %% 3  FanOut==>QDelivery          thick
    %% 4  QDelivery==>Deliver         thick
    %% 5  Deliver-->Target            solid
    %% 6  API-.->Client (202)         dashed
    %% 7  Deliver-->Deliver retry     solid
    %% 8  Beat==>QDelivery            thick
    %% 9  API-.->DB                   dashed
    %% 10 FanOut-.->DB                dashed
    %% 11 Deliver-.->DB               dashed
    %% 12 Beat-.->DB                  dashed
    linkStyle 6,9,10,11,12 stroke:#666,stroke-width:1px,stroke-dasharray: 5 5;
```

### Diagram legend

- **Solid / thick arrows** — task, message, and request flow (the delivery pipeline).
- **Dashed arrows** — Postgres reads and writes. Postgres is the source of truth; all delivery state lives there.
- **Pink** = storage, **blue** = compute, **orange** = Redis queues, **grey** = external actors.

## How it works

1. **Ingestion (synchronous).** A client calls `POST /events/` with an `X-API-Key`. FastAPI authenticates the tenant and runs `INSERT ... ON CONFLICT DO NOTHING` for idempotency, then enqueues a `deliver_event` task and returns `202 Accepted` without waiting for delivery.
2. **Fan-out.** `deliver_event` (on the `default` queue) reads the event and the tenant's matching endpoints, inserts one `pending` delivery row per endpoint, and dispatches one `deliver_to_endpoint` task per delivery to the `delivery` queue.
3. **Delivery.** `deliver_to_endpoint` (on the `delivery` queue) locks the delivery row with `SELECT ... FOR UPDATE SKIP LOCKED`, re-fetches fresh endpoint/event state, signs the payload with HMAC-SHA256, and POSTs to the endpoint with a 10s timeout. Success marks the row `success`.
4. **Retry.** Failures retry with exponential backoff (30s / 2m / 10m). After three attempts the row is marked `exhausted`.
5. **Recovery.** `Celery Beat` runs `recover_stuck_deliveries` every 5 minutes, scanning for `pending` rows whose `next_retry_at` is in the past and re-enqueueing them.

> The two Celery queues are isolated on purpose: a backlog of slow outbound HTTP calls on the `delivery` queue never blocks event ingestion via the `default` queue.

## Local Setup

Create your local `.env` file:

```bash
cp .env.example .env
```

Build and start the local Docker stack:

```bash
docker compose up -d --build
```

Seed local development data from inside the API container:

```bash
docker compose exec api python -m app.scripts.seed
```

Reset the database and seed fresh data:

```bash
docker compose exec api python -m app.scripts.seed --reset
```

## Run Tests

Start required services:

```bash
docker compose up -d postgres redis
```

Create test database once:

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE test_webhookdb;"
```

Run the test suite:

```bash
uv run pytest
```

## Migrations

```bash
docker-compose exec api alembic revision --autogenerate -m "your message"
docker-compose exec api alembic upgrade head
```
