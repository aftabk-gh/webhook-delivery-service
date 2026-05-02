# webhook-delivery-service
Production-grade webhook delivery infrastructure. Multi-tenant event ingestion, reliable HTTP delivery with retries, circuit breaker, HMAC signing, rate limiting, and semantic log search via pgvector.

## Run Tests

Start the required services:

```bash
docker compose up -d postgres redis
```

Create a test database once:

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE test_webhookdb;"
```

Run the test suite:

```bash
uv run pytest
```

## Create & Apply Migrations

```bash
docker-compose exec api alembic revision --autogenerate -m "your message"
docker-compose exec api alembic upgrade head
```
