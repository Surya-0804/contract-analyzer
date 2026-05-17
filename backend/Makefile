# ── Contract Analyzer — Backend Makefile ─────────────────────────────────────
# Uses `uv` for all Python operations.
# Run `make help` to see available commands.

.PHONY: help install dev lint format test run clean

PYTHON   := uv run python
UVICORN  := uv run uvicorn
APP      := app.main:app

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
	uv run pytest tests/ -v

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned."