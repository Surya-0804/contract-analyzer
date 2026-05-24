# Schema Modules

This document covers the modules in `app/schemas/`.

These schemas define the exact JSON shape expected back from the LLM at each stage.

## `app/schemas/segment.py`

### Purpose

Defines the clause extraction schema used by the segment node.

### Inputs and outputs

- Input: JSON from the segmentation prompt.
- Output: `SegmentOutput` containing a list of `ClauseBase` items.

### Key logic

- `ClauseBase` requires `clause_id`, `heading`, and `raw_text`.
- `SegmentOutput` wraps the clause list in a top-level `clauses` field.

### Pipeline fit

This is the first structured output shape in the pipeline.

### Example

```json
{
  "clauses": [
    {
      "clause_id": 1,
      "heading": "Notice Period",
      "raw_text": "Either party may terminate this agreement by giving 30 days notice."
    }
  ]
}
```

## `app/schemas/evaluate.py`

### Purpose

Defines the evaluation schema for clause classification and risk scoring.

### Inputs and outputs

- Input: JSON from the evaluation prompt.
- Output: `EvaluateOutput` containing `EvaluatedClause` items.

### Key logic

- Restricts `clause_type` to the implemented categories:
  `Non_Compete`, `Notice_Period`, `IP_Assignment`, `Lock_In`, `Compensation`, `Liability`, and `Other`.
- Restricts `risk_score` to integers from 1 to 5.
- Requires a short `risk_reasoning` string.

### Pipeline fit

This schema enriches the segmented clause list with risk metadata.

## `app/schemas/contradict.py`

### Purpose

Defines the contradiction detection response.

### Inputs and outputs

- Input: JSON from the contradiction prompt.
- Output: `ContradictOutput` with a `contradictions` list.

### Key logic

- Uses `default_factory=list` so an empty contradiction set is valid.
- Expects plain strings rather than nested objects.

### Pipeline fit

This schema carries the cross-clause findings into the final report stage.

### Example

```json
{
  "contradictions": [
    "Clause 4 states 30-day notice; Clause 11 states 60-day notice."
  ]
}
```

## `app/schemas/report.py`

### Purpose

Defines the final report payload returned by the report node.

### Inputs and outputs

- Input: JSON from the report prompt.
- Output: `ReportOutput` with one `final_report` markdown string.

### Key logic

- Keeps the report output minimal and explicit.
- Leaves markdown formatting inside the string instead of introducing nested fields.

### Pipeline fit

This is the last schema in the pipeline and feeds the API response body.

### Example

```json
{
  "final_report": "# Executive summary\n..."
}
```
