# Backend Repository Guidelines

Read this file before changing code under `backend/`. It is the working guide for
contributors and coding agents for the backend codebase.

## Scope

This file applies to all files under `backend/`.

- Follow the repo-root `AGENTS.md` first when it is relevant.
- If guidance conflicts, this file takes precedence for files inside `backend/`.

## Purpose

`contract-analyzer` is currently a Python backend for extracting structured clauses from
uploaded contract PDFs. The implemented scope is intentionally narrow:

- FastAPI API for file upload and analysis
- PDF ingestion and validation
- LLM-driven clause segmentation
- Shared pipeline state reserved for future evaluation, contradiction detection, and
  reporting

Do not document or expose unimplemented stages as working features.

## Project Structure

Backend layout:

- `main.py`: FastAPI entrypoint, CORS setup, middleware, `/health`, and router mounting
- `app/api/routes/analyze.py`: `POST /api/v1/analyze` endpoint
- `app/core/`: settings, logging, config, and LLM helpers
- `app/nodes/`: pipeline nodes including ingestion and segmentation
- `app/prompts/`: prompt message definitions used by nodes
- `app/schemas/`: Pydantic output schemas for structured LLM responses
- `app/state.py`: shared `ContractState` and `Clause` typed dictionaries
- `scripts/check_docs_updated.py`: docs policy helper
- `Makefile`, `pyproject.toml`, `uv.lock`: toolchain and dependency definitions

If you add tests, place them under `tests/`. The Makefile already assumes that path.

## Runtime Flow

Current request flow:

1. Client uploads a PDF to `POST /api/v1/analyze`.
2. The route rejects non-PDF filenames.
3. `IngestionNode.ingest_with_metadata(...)` validates bytes, opens the PDF with
   PyMuPDF, extracts markdown-like text with `pymupdf4llm`, and returns document
   metadata.
4. The route builds a `ContractState` containing `file_bytes`, `raw_pdf_text`,
   `document_metadata`, `clauses`, `contradictions`, and `final_report`.
5. `segment_node(...)` chunks long documents, calls the LLM for structured JSON,
   deduplicates clauses by normalized text, and stores token usage in
   `state["llm_metadata"]["segment"]`.
6. The API currently returns extracted clauses and a total count.

Important constraint: references in `state.py` to contradiction detection and reporting
are placeholders. Those stages are not wired yet.

## Development Commands

Run all commands from `backend/`.

- `uv sync`: install runtime dependencies
- `uv sync --extra dev --no-install-project`: install development dependencies
- `make run`: start the FastAPI dev server with reload on port `8000`
- `make lint`: run `ruff check .`
- `make format`: run `ruff format .`
- `make test`: run `pytest tests/ -v`
- `make docs-check`: require Markdown updates for code or config changes
- `make check`: run docs check, lint, and tests

Preferred local loop:

```bash
cd backend
uv sync --extra dev --no-install-project
make lint
make test
make run
```

## Pre-commit Workflow

The local hook configuration lives in `.pre-commit-config.yaml`.

Install hooks with:

```powershell
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

Hook behavior:

- `pre-commit` runs file hygiene checks, the docs policy check, `ruff check --fix`, and
  `ruff format`
- `pre-push` runs `make check`

## Coding Conventions

Use Python 3.12 features already present in the repo, including `|` union types and
`from __future__ import annotations` where useful.

Style expectations:

- 4-space indentation only
- Keep lines within Ruff's `100` character limit
- Use `snake_case` for modules, functions, variables, and prompt constants
- Use `PascalCase` for classes and Pydantic models
- Keep route handlers thin; move parsing, validation, and model logic into `app/core/`,
  `app/nodes/`, or `app/schemas/`
- Add short docstrings when behavior or failure mode is not obvious

Tooling:

- Ruff manages linting, import ordering, and formatting
- Do not add Black, isort, or autoflake workflows unless the toolchain changes

Normalize formatting only in files or sections touched by your change unless the task is
explicitly a formatting sweep.

## LLM And Prompt Rules

The LLM layer is centralized in `app/core/llm.py`.

- Use `get_llm(...)` rather than constructing `ChatOpenAI` directly
- Structured JSON responses are expected by default through
  `model_kwargs={"response_format": {"type": "json_object"}}`
- When parsing model output into a Pydantic schema, use existing helpers such as
  `invoke_json_llm(...)`
- Raise or propagate `LLMResponseError` for invalid JSON responses at the route boundary

Segmentation-specific rules:

- `segment_node(...)` chunks large inputs using `tiktoken`
- Clause deduplication is text-based and reassigns sequential `clause_id` values after
  deduplication
- Preserve usage metadata aggregation if you change chunking or prompt invocation
  behavior

When adding a new LLM-backed node:

1. Define a prompt in `app/prompts/`.
2. Define a strict output schema in `app/schemas/`.
3. Add a node in `app/nodes/`.
4. Log token and usage metadata.
5. Update docs in the same change.

## Testing Guidelines

The test stack is `pytest`, `pytest-asyncio`, and `httpx`.

Expected coverage for new backend behavior:

- Route tests for `POST /api/v1/analyze`
- Unit tests for `IngestionNode`
- Unit tests for chunking, clause deduplication, and JSON parsing behavior
- Failure-path tests for invalid PDFs, oversized files, and malformed LLM output

Naming conventions:

- Test files: `test_*.py`
- Test functions: `test_<behavior>()`

If you add or change behavior without tests, explain why in the task summary or PR.

## Commit And PR Guidelines

Use short imperative commit subjects.

- Start with a capitalized verb such as `Add`, `Fix`, `Refactor`, or `Update`
- Keep the subject focused on one logical change
- Avoid mixing unrelated refactors with feature work

PRs should include:

- a concise description of the change
- test and lint evidence
- notes on API contract changes when response shapes change
- sample request or response snippets when modifying `/api/v1/analyze`

## Configuration And Secrets

Settings are loaded from `.env` via `app/core/settings.py`.

Relevant environment variables:

- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `OPENROUTER_MODEL`
- `OPENAI_TIMEOUT_SECONDS`
- `OPENAI_MAX_RETRIES`
- `LLM_WARN_INPUT_TOKENS`

Rules:

- Never commit secrets
- When adding a new setting, define it in `Settings` and give it a sensible default
  where possible
- If a setting affects runtime behavior, update this file and relevant README content in
  the same change

## Documentation Policy

Documentation updates are part of the change, not follow-up work. If you modify:

- API behavior
- environment variables
- prompts or pipeline stages
- local development commands
- backend contributor workflow

then update the relevant Markdown in the same commit.

At minimum, keep these accurate:

- `backend/AGENTS.md`
- `backend/README.md`
- repo-root `AGENTS.md` when repo-wide guidance changes

Use `scripts/check_docs_updated.py` when the docs policy is enforced in local workflows.

## Extension Notes

The current `ContractState` already reserves fields for future stages such as clause
evaluation, contradiction detection, and final reporting. If you implement those stages:

1. Extend state deliberately rather than creating parallel ad hoc payloads.
2. Keep each stage in its own node file.
3. Define schemas before parsing model output.
4. Return stable JSON shapes from the API.
5. Add tests and update docs together.
