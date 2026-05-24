# Node Modules

This document covers the modules in `app/nodes/`.

## Pipeline summary

The route in `app/api/routes/analyze.py` runs these nodes in order:

1. `IngestionNode.ingest_with_metadata(...)`
2. `segment_node(...)`
3. `evaluate_node(...)`
4. `contradict_node(...)`
5. `report_node(...)`

Each node reads and updates `ContractState`.

## `app/nodes/ingestion.py`

### Purpose

Validates an uploaded PDF and extracts text plus basic metadata.

### Inputs and outputs

- Input: raw PDF bytes.
- Output: extracted text and a metadata dictionary with `page_count` and `file_size_bytes`.

### Key logic

- Rejects non-bytes input and oversized files.
- Opens the PDF with PyMuPDF.
- Uses `pymupdf4llm.to_markdown(...)` to preserve structure in the extracted text.
- Raises a `ValueError` when the PDF is invalid or contains no extractable text.

### Pipeline fit

This is the entry point for content extraction. Everything downstream depends on `raw_pdf_text`.

### Example

```python
node = IngestionNode()
text, metadata = node.ingest_with_metadata(file_bytes)
```

## `app/nodes/segment.py`

### Purpose

Splits the extracted contract text into individual clauses.

### Inputs and outputs

- Input: `ContractState` with `raw_pdf_text`.
- Output: updated `ContractState` with `clauses` and `llm_metadata["segment"]`.

### Key logic

- Estimates prompt and document token counts.
- Chunks large documents using `tiktoken`.
- Calls the LLM with the segment prompt for each chunk.
- Deduplicates clauses by normalized `raw_text`.
- Reassigns sequential `clause_id` values after deduplication.

### Pipeline fit

This stage converts one document string into the structured clause list used by the rest of the pipeline.

### Example

`chunk_text(...)` returns one chunk for short text and overlapping chunks for longer text.

## `app/nodes/evaluate.py`

### Purpose

Classifies each clause and assigns a risk score with short reasoning.

### Inputs and outputs

- Input: `ContractState` with `clauses`.
- Output: updated `ContractState` with enriched clause fields:
  `clause_type`, `risk_score`, and `risk_reasoning`.

### Key logic

- Serializes clauses into JSON for the prompt.
- Serializes static guidance from `app/utils/knowledge_base.py`.
- Calls the LLM once for the full clause list.
- Merges the returned evaluation back into each clause.
- Falls back to `Other` with a low risk score if a clause comes back unevaluated.

### Pipeline fit

This stage adds the risk annotations used by contradiction detection and report generation.

## `app/nodes/contradict.py`

### Purpose

Finds confirmed logical or numerical contradictions across the evaluated clauses.

### Inputs and outputs

- Input: `ContractState` with evaluated `clauses`.
- Output: updated `ContractState` with `contradictions` and `llm_metadata["contradict"]`.

### Key logic

- Serializes the clause list, including risk annotations.
- Calls the LLM with instructions to avoid speculation.
- Stores only the returned contradiction strings.
- Returns an empty list when there are no clauses.

### Pipeline fit

This stage compares clauses against each other rather than evaluating them individually.

## `app/nodes/report.py`

### Purpose

Builds the final markdown report from clauses and contradiction results.

### Inputs and outputs

- Input: `ContractState` with `clauses` and `contradictions`.
- Output: updated `ContractState` with `final_report` and `llm_metadata["report"]`.

### Key logic

- Serializes clauses and contradictions into JSON.
- Calls the LLM with a fixed report structure.
- Stores the returned markdown string in `final_report`.

### Pipeline fit

This is the final synthesis stage. The API returns this report directly.

### Example

The report prompt requires these sections:

1. Executive summary
2. High-risk clauses
3. Contradictions
4. Safe clauses
5. Disclaimer
