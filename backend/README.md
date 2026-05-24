# Contract Analyzer Backend

Python FastAPI backend for extracting clauses from uploaded contract PDFs, evaluating clause risk, checking for contradictions, and generating a concise markdown report through a hybrid pipeline plus lightweight agent controller.

## Project overview

The backend currently implements a narrow contract-analysis workflow:

- PDF upload through `POST /api/v1/analyze`
- PDF text extraction with PyMuPDF and `pymupdf4llm`
- Lightweight controller that plans and executes analysis steps
- LLM-based clause segmentation
- LLM-based clause evaluation using a static knowledge base
- LLM-based contradiction detection across clauses
- LLM-based final markdown report generation

The backend does not include persistent storage, user accounts, or live web research. It is not a general autonomous agent. The controller adds small agent-like behavior on top of a fixed set of pipeline nodes.

## Hybrid controller flow

The analyze route sets the goal to `analyze contract` and runs a small controller. The controller:

- builds a plan as a list of step names
- decides whether a step should run from current state
- allows one retry for selected low-confidence results

The default plan is:

1. `segment`
2. `evaluate`
3. `contradict`
4. `report`

### What each stage does

#### `segment`

- Reads extracted contract text from the ingestion step.
- Chunks long documents by token count.
- Calls the LLM to split the contract into distinct clauses.
- Deduplicates clauses by normalized text and reassigns sequential clause IDs.

#### `evaluate`

- Takes the clause list from `segment`.
- Classifies each clause into one of the implemented categories:
  `Non_Compete`, `Notice_Period`, `IP_Assignment`, `Lock_In`, `Compensation`, `Liability`, `Other`.
- Assigns a `risk_score` from 1 to 5 and short reasoning.
- Uses only the static baselines in `app/utils/knowledge_base.py`.

#### `contradict`

- Reviews the evaluated clause list together.
- Returns only confirmed logical or numerical contradictions.
- Avoids speculative or hypothetical conflicts.
- The controller skips this step when there are fewer than 2 clauses.

#### `report`

- Builds the final markdown report from the evaluated clauses and contradiction list.
- Produces sections for summary, high-risk clauses, contradictions, safe clauses, and disclaimer.

## Minimal agent behavior

The system is partially agent-like in a narrow, production-friendly way:

- Goal: the request sets `goal = "analyze contract"`
- Plan: the controller stores a step list in `state["plan"]`
- Shared memory: all stages read and update `ContractState`
- Conditional execution: the controller can skip `contradict` for very small clause sets
- Basic iteration: the controller retries `evaluate` once when heuristics mark the output as low confidence, and retries `contradict` once when returned wording looks unclear

This keeps the implementation simple while avoiding a fully hardcoded one-pass route.

## Request flow

1. The client uploads a PDF file.
2. The route rejects non-PDF filenames.
3. `IngestionNode.ingest_with_metadata(...)` validates the file, opens the PDF, and extracts markdown-like text.
4. The backend creates a shared `ContractState`.
5. The controller builds and executes a plan, usually `segment -> evaluate -> contradict -> report`.
6. The API returns the clauses, contradictions, final report, and total clause count.

## Setup

Run commands from `backend/`.

### Install dependencies

```powershell
uv sync
```

For development tools:

```powershell
uv sync --extra dev --no-install-project
```

### Common commands

```powershell
make run
make lint
make format
make test
make docs-check
make check
```

## Configuration

Settings load from `backend/.env`.

Relevant environment variables:

- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `OPENROUTER_MODEL`
- `OPENAI_TIMEOUT_SECONDS`
- `OPENAI_MAX_RETRIES`
- `LLM_WARN_INPUT_TOKENS`
- `SEGMENT_CHUNK_MAX_TOKENS`
- `SEGMENT_CHUNK_OVERLAP_TOKENS`
- `SEGMENT_CHUNK_DELAY_SECONDS`

## API

### `POST /api/v1/analyze`

Analyzes one uploaded PDF contract.

#### Request

- Content type: `multipart/form-data`
- Field: `file`
- Accepted file type: `.pdf`

#### Success response

```json
{
  "clauses": [
    {
      "clause_id": 1,
      "heading": "Notice Period",
      "raw_text": "Either party may terminate this agreement by giving 30 days notice.",
      "clause_type": "Notice_Period",
      "risk_score": 2,
      "risk_reasoning": "The notice period appears within a common range."
    }
  ],
  "contradictions": [],
  "final_report": "# Executive summary\n...",
  "total": 1
}
```

#### Error behavior

- Returns `400` for non-PDF uploads, invalid PDFs, oversized files, or PDFs with no extractable text.
- Returns `502` when the LLM returns invalid JSON.
- Returns `503` when the upstream model provider rate-limits requests.
- Returns `502` for other provider-side HTTP failures surfaced by the LLM client.

## Limitations

- Clause evaluation uses a static knowledge base in `app/utils/knowledge_base.py`.
- The backend does not perform web search or fetch live legal references.
- Risk scores and contradictions depend on LLM output quality.
- Scanned PDFs without extractable text are rejected instead of being OCR-processed here.
- The API currently processes one uploaded file at a time and keeps state in memory for the request only.

## Docs

Module-level backend docs live in `docs/`:

- `docs/core.md`
- `docs/nodes.md`
- `docs/agent_controller.md`
- `docs/prompts.md`
- `docs/schemas.md`
- `docs/docs_update_policy.md`
