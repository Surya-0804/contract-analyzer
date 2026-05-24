# Agent Controller

This document explains the lightweight controller in `app/nodes/agent_controller.py`.

## Purpose

The backend is no longer a purely hardcoded one-pass route. It now uses a small controller that adds limited agent-style behavior while keeping the existing nodes intact.

The controller is intentionally narrow:

- one goal: `analyze contract`
- one shared memory object: `ContractState`
- one simple plan made of existing step names
- one retry at most for selected low-confidence steps

## Inputs and outputs

### Input

- `ContractState` after PDF ingestion
- existing node functions:
  `segment_node(...)`, `evaluate_node(...)`, `contradict_node(...)`, `report_node(...)`

### Output

Updated `ContractState` with:

- `goal`
- `plan`
- `step_logs`
- `retry_counts`
- `clauses`
- `contradictions`
- `final_report`

## Planning

The controller creates a plan as a list of strings.

Typical plan:

```python
["segment", "evaluate", "contradict", "report"]
```

Planning is state-based rather than model-generated:

- if there are no clauses yet, run `segment`
- if clauses are not evaluated yet, run `evaluate`
- if there are at least 2 clauses, run `contradict`
- always finish with `report`

This keeps planning simple and deterministic.

## Execution

The controller executes the plan step by step and records what happened in `state["step_logs"]`.

Each log entry includes:

- `step`
- `status`
- `detail`

Possible statuses include:

- `completed`
- `skipped`
- `retry`

## Conditional behavior

The controller can skip `contradict` when there are too few clauses to compare.

Current rule:

- skip contradiction detection when clause count is less than `2`

## Basic iteration

The controller supports one retry for selected steps.

### Evaluation retry

`evaluate` is retried once when heuristics mark the result as low confidence.

Current low-confidence signals:

- one or more clauses were missing from the evaluation response and had to fall back
- every evaluated clause came back as `Other`

### Contradiction retry

`contradict` is retried once when returned contradiction text looks uncertain.

Current unclear markers include phrases such as:

- `unclear`
- `may conflict`
- `might conflict`
- `potential conflict`

## How it fits into the system

Request flow now looks like this:

1. Ingest PDF
2. Initialize `ContractState`
3. Set goal to `analyze contract`
4. Build plan
5. Execute steps conditionally
6. Retry selected steps once if needed
7. Return the same API response contract as before

## What it is and is not

This is a minimal agent-style controller.

It is:

- goal-oriented
- plan-driven
- stateful
- conditionally executable
- able to retry selected steps once

It is not:

- a general autonomous agent
- a tool-using system
- a dynamic planner that invents new actions
- a multi-agent architecture
