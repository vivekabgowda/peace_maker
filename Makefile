# BKN AI Capital — developer commands.
.DEFAULT_GOAL := help
.PHONY: help up down logs migrate seed backend-shell \
        be-install be-test be-lint be-format be-typecheck \
        fe-install fe-test fe-lint fe-build test lint

BE := backend
FE := frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

## --- Docker (full stack) ---------------------------------------------------
up: ## Start the dev stack (Postgres, Redis, backend, frontend, n8n)
	./scripts/dev-up.sh -d
down: ## Stop the dev stack
	docker compose down
logs: ## Tail all logs
	docker compose logs -f
migrate: ## Apply DB migrations inside the backend container
	docker compose exec backend alembic upgrade head
seed: ## Seed the initial admin user
	docker compose exec backend python -m scripts.seed
backend-shell: ## Open a shell in the backend container
	docker compose exec backend sh

## --- Backend (local) -------------------------------------------------------
be-install: ## Install backend dev dependencies
	cd $(BE) && pip install -e ".[dev]"
be-test: ## Run backend tests
	cd $(BE) && pytest
be-lint: ## Lint backend (ruff)
	cd $(BE) && ruff check app tests scripts
be-format: ## Format backend (black + ruff --fix)
	cd $(BE) && black app tests scripts migrations && ruff check --fix app tests scripts
be-typecheck: ## Typecheck backend (mypy)
	cd $(BE) && mypy app

## --- Frontend (local) ------------------------------------------------------
fe-install: ## Install frontend dependencies
	cd $(FE) && npm ci
fe-test: ## Run frontend tests
	cd $(FE) && npm run test
fe-lint: ## Lint + typecheck frontend
	cd $(FE) && npm run lint && npm run typecheck
fe-build: ## Production build of the frontend
	cd $(FE) && npm run build

## --- Aggregate -------------------------------------------------------------
lint: be-lint be-typecheck fe-lint ## Lint everything
test: be-test fe-test ## Test everything
