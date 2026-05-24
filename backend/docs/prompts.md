# Prompt Modules

This document covers the modules in `app/prompts/`.

These files keep prompt text separate from node logic so prompt changes are easier to review.

## `app/prompts/segment.py`

### Purpose

Defines the messages used to split a contract into individual clauses.

### Inputs and outputs

- Input: `contract_text`.
- Output: prompt messages consumed by `ChatPromptTemplate.from_messages(...)`.

### Key logic

- Tells the model to extract every distinct clause.
- Requires `raw_text` to preserve the original wording.
- Requires sequential clause numbering and a strict JSON shape.

### Pipeline fit

Used only by `segment_node(...)`.

### Example

The human message injects the uploaded document text into `{contract_text}`.

## `app/prompts/evaluate.py`

### Purpose

Defines the messages used to classify clauses and assign risk scores.

### Inputs and outputs

- Input: `baselines` and `clauses_json`.
- Output: prompt messages for the evaluate stage.

### Key logic

- Restricts classification to the implemented clause categories.
- Tells the model to score risk from 1 to 5.
- Requires one output object per input clause.

### Pipeline fit

Used only by `evaluate_node(...)`.

### Example

The human message combines serialized baseline rules with the serialized clause list.

## `app/prompts/contradict.py`

### Purpose

Defines the messages used to detect contradictions across clauses.

### Inputs and outputs

- Input: `clauses_json`.
- Output: prompt messages for contradiction detection.

### Key logic

- Instructs the model to return only confirmed contradictions.
- Rejects speculation and duplicate findings.
- Requires a compact JSON response with a `contradictions` list.

### Pipeline fit

Used only by `contradict_node(...)`.

## `app/prompts/report.py`

### Purpose

Defines the messages used to generate the final markdown report.

### Inputs and outputs

- Input: `clauses_json` and `contradictions_json`.
- Output: prompt messages for report generation.

### Key logic

- Enforces a fixed report structure.
- Restricts the report to the provided clause and contradiction data.
- Requires the result to be JSON containing a markdown string.

### Pipeline fit

Used only by `report_node(...)`.

### Example

The report must include these sections:

1. Executive summary
2. High-risk clauses
3. Contradictions
4. Safe clauses
5. Disclaimer
