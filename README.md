# webhook-delivery-service

Production-grade webhook delivery infrastructure. Multi-tenant event ingestion, reliable HTTP delivery with retries, circuit breaker, HMAC signing, rate limiting, and semantic log search via pgvector.

Built for learning senior backend/distributed systems concepts.

## Stack

FastAPI, PostgreSQL, Redis, Celery, Docker, pgvector, OpenAI embeddings.

## Important Files

- `AGENTS.md` — mandatory AI behavior rules. Follow always.
- `BREAKDOWN.md` — step-by-step project roadmap.
- `docs/adr/` — architecture decisions.
- `prompts/` — reusable learning/review prompts.

## Current Development Rules

1. Follow `AGENTS.md` first.
2. Use `BREAKDOWN.md` only to understand the current step.
3. Do not implement anything listed under "Write Yourself".
4. Keep architecture: API → Service → Data Layer → DB.
5. Enforce tenant isolation on every tenant-owned query.
6. If prompt starts with `DISCUSS:`, give hints only.
7. If prompt starts with `IMPLEMENT:`, generate allowed production-ready code.
8. If a task conflicts with `AGENTS.md`, follow `AGENTS.md`.

## Current Step

Currently working on: **Step 5**

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

## Seed Data

Start the local Docker stack:

```bash
docker compose up -d
```

Seed local development data from inside the API container:

```bash
docker compose exec api python -m app.scripts.seed
```

Reset the database and seed fresh data:

```bash
docker compose exec api python -m app.scripts.seed --reset
```

## Migrations

```bash
docker-compose exec api alembic revision --autogenerate -m "your message"
docker-compose exec api alembic upgrade head
```
