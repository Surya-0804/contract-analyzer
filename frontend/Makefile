# ── Contract Analyzer — Frontend Makefile ─────────────────────────────────────
# Uses `pnpm` for all JavaScript operations.
# Run `make help` to see available commands.

.PHONY: help install dev build preview lint format clean

help:
	@echo ""
	@echo "Frontend (Vite + React)"
	@echo ""
	@echo "make install     Install dependencies"
	@echo "make dev         Start dev server"
	@echo "make build       Build production bundle"
	@echo "make preview     Preview production build"
	@echo "make lint        Run ESLint"
	@echo "make format      Format code"
	@echo "make clean       Remove node_modules and lockfile"
	@echo ""

install:
	pnpm install

dev:
	pnpm dev

build:
	pnpm build

preview:
	pnpm preview

lint:
	pnpm exec eslint . --ext .ts,.tsx

format:
	pnpm exec prettier --write .

clean:
	rm -rf node_modules pnpm-lock.yaml dist
	