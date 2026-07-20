.PHONY: install lint test typecheck web-build compose-up compose-down migrate

install:
	uv sync --extra dev
	pnpm install

lint:
	uv run ruff check .
	pnpm lint

typecheck:
	uv run mypy packages/proactive_core/proactive_core
	pnpm typecheck

test:
	uv run pytest
	pnpm test

web-build:
	pnpm --filter @proactive/web build

compose-up:
	docker compose --profile core up -d --build

compose-down:
	docker compose --profile core down

migrate:
	uv run alembic upgrade head

