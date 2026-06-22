.PHONY: help up down logs ps build test lint fmt clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack (postgres + localstack + api) in the background
	@test -f .env || cp .env.example .env
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f --tail=100

ps: ## Show running containers
	docker compose ps

build: ## Rebuild images
	docker compose build

test: ## Run the backend test suite (locally)
	cd backend && python -m pytest

lint: ## Run ruff checks
	cd backend && ruff check .

fmt: ## Auto-format with ruff
	cd backend && ruff format .

clean: ## Stop the stack and remove volumes + localstack state
	docker compose down -v
	rm -rf volume
