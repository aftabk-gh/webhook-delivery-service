FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY . .

RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"

USER app
