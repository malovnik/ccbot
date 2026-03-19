.PHONY: check test lint format typecheck audit start stop restart

check: lint format typecheck test  ## Run all checks (CI equivalent)

test:  ## Run tests
	uv run pytest tests/ -q

lint:  ## Run linter
	uv run ruff check src/ tests/

format:  ## Check formatting
	uv run ruff format --check src/ tests/

fix:  ## Auto-fix lint and format issues
	uv run ruff check src/ tests/ --fix
	uv run ruff format src/ tests/

typecheck:  ## Run type checker
	uv run pyright src/ccbot/

audit:  ## Audit dependencies for vulnerabilities
	uv run pip-audit

start:  ## Start ccbot in tmux
	./scripts/start.sh

stop:  ## Stop ccbot
	./scripts/stop.sh

restart:  ## Restart ccbot
	./scripts/restart.sh

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
