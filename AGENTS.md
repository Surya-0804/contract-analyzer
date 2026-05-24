# Repository Guidelines

Read this file before changing code. It is the working guide for contributors and coding agents in this repository.

## Repo Purpose

`contract-analyzer` is a Python backend for extracting structured clauses from uploaded contract PDFs. The current implementation is intentionally narrow:

- FastAPI API for file upload and analysis
- PDF ingestion and validation
- LLM-driven clause segmentation
- Shared pipeline state for future evaluation, contradiction detection, and reporting

The repository does not yet include a frontend, persistent storage, or a full multi-node LangGraph runtime. Keep changes aligned with the current scope unless the task explicitly expands it.

## Project Structure

Top-level layout:

- `backend/main.py`: FastAPI entrypoint, CORS setup, middleware, `/health`, and router mounting.
- `backend/app/api/routes/analyze.py`: `POST /api/v1/analyze` endpoint.
- `backend/app/core/`: settings, logging, config, and LLM helpers.
- `backend/app/nodes/`: pipeline nodes. `ingestion.py` extracts text from PDFs and `segment.py` turns raw text into clauses.
- `backend/app/prompts/`: prompt message definitions used by nodes.
- `backend/app/schemas/`: Pydantic output schemas for structured LLM responses.
- `backend/app/state.py`: shared `ContractState` and `Clause` typed dictionaries.
- `backend/scripts/check_docs_updated.py`: docs policy helper.
- `backend/Makefile`, `backend/pyproject.toml`, `backend/uv.lock`: toolchain and dependency definitions.

If you add tests, place them under `backend/tests/`. The Makefile already assumes that path.

## Runtime Flow

Current request flow:

1. Client uploads a PDF to `POST /api/v1/analyze`.
2. The route rejects non-PDF filenames.
3. `IngestionNode.ingest_with_metadata(...)` validates bytes, opens the PDF with PyMuPDF, extracts markdown-like text with `pymupdf4llm`, and returns document metadata.
4. The route builds a `ContractState` containing `file_bytes`, `raw_pdf_text`, `document_metadata`, `clauses`, `contradictions`, and `final_report`.
5. `segment_node(...)` chunks long documents, calls the LLM for structured JSON, deduplicates clauses by normalized text, and stores token usage in `state["llm_metadata"]["segment"]`.
6. The API currently returns extracted clauses and a total count.

Important constraint: despite references in `state.py` to later stages like contradiction detection and reporting, those stages are not wired yet. Do not document or expose them as working features unless you implement them.

## Development Commands

Run all commands from `backend/`.

- `uv sync`: install runtime dependencies.
- `uv sync --extra dev --no-install-project`: install development dependencies.
- `make run`: start the FastAPI dev server with reload on port `8000`.
- `make lint`: run `ruff check .`.
- `make format`: run `ruff format .`.
- `make test`: run `pytest tests/ -v`.

Preferred local loop:

```bash
cd backend
uv sync --extra dev --no-install-project
make lint
make test
make run
```

## Coding Conventions

Use Python 3.12 features already present in the repo, including `|` union types and `from __future__ import annotations` where useful.

Style expectations:

- 4-space indentation only. Do not introduce tabs.
- Keep lines within Ruff’s `100` character limit.
- Use `snake_case` for modules, functions, variables, and prompt constants.
- Use `PascalCase` for classes and Pydantic models.
- Keep route handlers thin; move parsing, validation, and model logic into `app/core/`, `app/nodes/`, or `app/schemas/`.
- Add short docstrings when behavior or failure mode is not obvious.

Tooling:

- Linting and import rules are managed by Ruff.
- Formatting is also handled by Ruff in this repo.

Before editing, note that some existing files contain inconsistent indentation or formatting. Normalize only what your change touches unless the task is explicitly a formatting sweep.

## LLM And Prompt Rules

The LLM layer is centralized in `backend/app/core/llm.py`.

- Use `get_llm(...)` rather than constructing `ChatOpenAI` directly.
- Structured JSON responses are expected by default through `model_kwargs={"response_format": {"type": "json_object"}}`.
- When parsing model output into a Pydantic schema, use the existing helpers such as `invoke_json_llm(...)`.
- Raise or propagate `LLMResponseError` for invalid JSON responses at the route boundary.

Segmentation-specific rules:

- `segment_node(...)` chunks large inputs using `tiktoken`.
- Clause deduplication is text-based and reassigns sequential `clause_id` values after deduplication.
- Preserve usage metadata aggregation if you change chunking or prompt invocation behavior.

When adding a new LLM-backed node, follow the same pattern:

1. Define a prompt in `app/prompts/`.
2. Define a strict output schema in `app/schemas/`.
3. Add a node in `app/nodes/`.
4. Log token and usage metadata.
5. Update docs in the same change.

## Testing Guidelines

The declared test stack is `pytest`, `pytest-asyncio`, and `httpx`. There are currently no committed tests under `backend/tests/`, but new work should add them.

Expected test coverage for new code:

- Route tests for `POST /api/v1/analyze`
- Unit tests for `IngestionNode`
- Unit tests for `chunk_text`, clause deduplication, and JSON parsing behavior
- Failure-path tests for invalid PDFs, oversized files, and malformed LLM output

Naming conventions:

- Test files: `test_*.py`
- Test functions: `test_<behavior>()`

Example:

```bash
cd backend
make test
```

If you add or change behavior without tests, explain why in the PR or task summary.

## Commit And PR Guidelines

Recent history uses short imperative commit subjects, for example:

- `Add analyze route for contract processing with PDF validation and ingestion`
- `Refactor code structure for improved readability and maintainability`

Follow that style:

- Start with a capitalized verb: `Add`, `Refactor`, `Fix`, `Update`.
- Keep the subject focused on one logical change.
- Avoid mixing refactors with feature work unless tightly coupled.

Pull requests should include:

- A concise description of the change
- Test and lint evidence
- Notes on API contract changes if response shapes changed
- Sample request or response snippets when modifying `/api/v1/analyze`

## Configuration And Secrets

Settings are loaded from `backend/.env` via `backend/app/core/settings.py`.

Relevant environment variables:

- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `OPENROUTER_MODEL`
- `OPENAI_TIMEOUT_SECONDS`
- `OPENAI_MAX_RETRIES`
- `LLM_WARN_INPUT_TOKENS`

Rules:

- Never commit secrets.
- When adding a new setting, define it in `Settings` and give it a sensible default where possible.
- If a setting affects runtime behavior, update this file and any user-facing README content in the same change.

## Documentation Policy

Documentation updates are part of the change, not follow-up work. If you modify:

- API behavior
- environment variables
- prompts or pipeline stages
- local development commands

then update the relevant Markdown in the same commit. At minimum, keep `AGENTS.md` accurate. Use `backend/scripts/check_docs_updated.py` if the docs policy is being enforced in local workflows.

## Extension Notes

The current `ContractState` already reserves fields for future stages such as clause evaluation, contradiction detection, and final reporting. If you implement those stages:

1. Extend state deliberately rather than creating parallel ad hoc payloads.
2. Keep each stage in its own node file.
3. Define schemas before parsing model output.
4. Return stable JSON shapes from the API.
5. Add tests and update docs together.
