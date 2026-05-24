# Core Modules

This document covers the modules in `app/core/`.

## `app/core/settings.py`

### Purpose

Loads runtime settings from `backend/.env` and caches them for reuse.

### Inputs and outputs

- Input: environment variables such as `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENROUTER_MODEL`, and chunking settings.
- Output: a `Settings` object returned by `get_settings()`.

### Key logic

- Uses `pydantic-settings` to read `.env` values.
- Defines defaults for LLM timeouts, retries, token warnings, and segment chunk sizing.
- Uses `@lru_cache` so settings are parsed once per process.

### Pipeline fit

This module supplies configuration to the LLM helpers and the segment node.

### Example

```python
from app.core.settings import get_settings

settings = get_settings()
model_name = settings.openrouter_model
```

## `app/core/config.py`

### Purpose

Provides a minimal `Settings` object and exports `settings`.

### Inputs and outputs

- Input: values from `backend/.env`.
- Output: `settings`, an instance of the local `Settings` class.

### Key logic

- Resolves the backend root.
- Configures `pydantic-settings` to load `.env`.

### Pipeline fit

This module is currently a lightweight config holder. The active pipeline mainly uses `app/core/settings.py`.

## `app/core/llm.py`

### Purpose

Centralizes model creation, JSON parsing, token estimation, and LLM error handling.

### Inputs and outputs

- Input: model names, prompts, payload dictionaries, and output schema classes.
- Output: configured LLM clients, parsed Pydantic models, usage metadata, or structured errors.

### Key logic

- `get_llm(...)` creates `ChatOpenAI` with JSON output enabled by default.
- `estimate_tokens(...)` uses `tiktoken` to approximate prompt and document size.
- `parse_model_json(...)` sanitizes model text before validating it with a Pydantic schema.
- `invoke_json_llm(...)` runs a prompt, parses JSON, and converts provider failures into backend-friendly exceptions.
- `invoke_structured_llm(...)` supports LangChain structured output flows, though the current nodes use `invoke_json_llm(...)`.

### Pipeline fit

Every LLM-backed stage depends on this module:

- `segment_node(...)`
- `evaluate_node(...)`
- `contradict_node(...)`
- `report_node(...)`

### Example

```python
result, metadata = await invoke_json_llm(
    llm,
    prompt,
    payload,
    OutputSchema,
)
```

## `app/core/logging_utils.py`

### Purpose

Provides request-aware logging helpers and root logger configuration.

### Inputs and outputs

- Input: log messages, optional request IDs, and logging config values.
- Output: formatted log records and `AppLogger` wrappers.

### Key logic

- Stores the current request ID in a `ContextVar`.
- `RequestFormatter` injects timestamps and request IDs into log output.
- `configure_logging(...)` attaches file and console handlers.
- `get_logger(...)` returns a thin wrapper that prefixes logs with request context.

### Pipeline fit

Used across the backend so node and LLM logs can be correlated during a request.

### Example

```python
logger = get_logger(__name__)
logger.info("segment_node: starting clause extraction")
```
