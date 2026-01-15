.PHONY: help sync lint format types test ci verify fix clean docs docs-serve

# Default target
help:
	@echo "🔧 CI Targets:"
	@echo "  make ci       - Run ALL CI checks (lint + format + types + test)"
	@echo "  make verify   - Sync dependencies + run all CI checks"
	@echo "  make lint     - Run ruff linter"
	@echo "  make format   - Check code formatting"
	@echo "  make types    - Run pyright type checker"
	@echo "  make test     - Run pytest with coverage"
	@echo ""
	@echo "🛠️  Development Targets:"
	@echo "  make sync     - Install/sync all dependencies"
	@echo "  make fix      - Auto-fix lint and format issues"
	@echo "  make clean    - Remove build artifacts and caches"
	@echo ""
	@echo "📚 Documentation Targets:"
	@echo "  make docs       - Build documentation"
	@echo "  make docs-serve - Serve docs locally with live reload"

sync:
	uv sync --locked

lint:
	uv run --locked ruff check --diff

format:
	uv run --locked ruff format --diff

types:
	uv run --locked pyright

test:
	uv run --locked pytest

ci: lint format types test
	@echo ""
	@echo "✅ All CI checks passed!"

verify: sync ci

fix:
	uv run --locked ruff check --fix
	uv run --locked ruff format

clean:
	rm -rf .pytest_cache .ruff_cache .pyright coverage dist build site
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docs:
	uv run --locked --group docs mkdocs build

docs-serve:
	uv run --locked --group docs mkdocs serve --dev-addr localhost:8010 --livereload
