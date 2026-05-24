# ── Contract Analyzer — Backend Makefile ─────────────────────────────────────
# Uses `uv` for all Python operations.
# Run `make help` to see available commands.

.PHONY: help install dev lint format test docs-check check run clean

PYTHON   := uv run python
UVICORN  := uv run uvicorn
APP      := main:app

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Contract Analyzer — Backend"
	@echo ""
	@echo "  make install     Install all dependencies (production)"
	@echo "  make dev         Install dev + production dependencies"
	@echo "  make run         Start FastAPI dev server (hot-reload)"
	@echo "  make lint        Run ruff linter"
	@echo "  make format      Run ruff formatter"
	@echo "  make test        Run pytest"
	@echo "  make docs-check  Require Markdown updates for code/config changes"
	@echo "  make check       Run docs check, lint, and tests"
	@echo "  make clean       Remove __pycache__ and .pytest_cache"
	@echo ""

# ── Install ───────────────────────────────────────────────────────────────────
install:
	uv sync

dev:
	uv sync --extra dev --no-install-project
	
# ── Run ───────────────────────────────────────────────────────────────────────
run:
	$(UVICORN) $(APP) --reload --host 0.0.0.0 --port 8000

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	uv run ruff check .

format:
	uv run ruff format .

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	@if [ -d tests ]; then \
		uv run pytest tests/ -v; \
	else \
		echo "No tests/ directory present; skipping pytest."; \
	fi

docs-check:
	uv run python scripts/check_docs_updated.py

check: docs-check
	uv run ruff check .
	@if [ -d tests ]; then \
		uv run pytest tests/ -v; \
	else \
		echo "No tests/ directory present; skipping pytest."; \
	fi

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned."
