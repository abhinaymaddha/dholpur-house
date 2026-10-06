.PHONY: help install dev test ingest clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies (incl. dev)
	pip install -r requirements-dev.txt

dev: ## Run the API with auto-reload on :8000
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run tests
	pytest tests/ -v

ingest: ## Load a Telegram export: make ingest EXPORT="/path/to/ChatExport_..."
	python -m app.ingest "$(EXPORT)"

clean: ## Remove caches
	find . -type d -name __pycache__ -exec rm -r {} +
	rm -rf .pytest_cache
