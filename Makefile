.PHONY: help lint lint-fix format typecheck quality

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*##' Makefile | awk -F '##' '{printf "  %-15s %s\n", $$1, $$2}'

lint:      ## Lint code
	uv run ruff check .

lint-fix:  ## Lint and auto-fix
	uv run ruff check . --fix

format:    ## Format code
	uv run ruff format .

typecheck: ## Run mypy
	uv run mypy .

quality:   ## Fix, format and typecheck
	uv run ruff check . --fix && uv run ruff format . && uv run mypy .