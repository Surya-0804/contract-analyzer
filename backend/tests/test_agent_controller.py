from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

import pytest

from app.nodes import agent_controller
from app.state import ContractState


@pytest.fixture
def base_state() -> ContractState:
    return {
        "goal": "analyze contract",
        "raw_pdf_text": "contract text",
        "clauses": [],
        "contradictions": [],
        "final_report": "",
        "step_logs": [],
        "retry_counts": {},
    }


@pytest.fixture
def clause_pair() -> list[dict]:
    return [
        {"clause_id": 1, "heading": "Notice", "raw_text": "30 days notice"},
        {"clause_id": 2, "heading": "Liability", "raw_text": "Unlimited liability"},
    ]


@pytest.fixture
def run_controller(monkeypatch) -> Callable[..., tuple[ContractState, list[str], dict[str, int]]]:
    async def _run(
        state: ContractState,
        *,
        segmented_clauses: list[dict],
        evaluate_low_confidence_on_calls: set[int] | None = None,
        contradict_unclear_on_calls: set[int] | None = None,
    ) -> tuple[ContractState, list[str], dict[str, int]]:
        calls: list[str] = []
        counters = {"evaluate": 0, "contradict": 0}
        evaluate_low_confidence_on_calls = evaluate_low_confidence_on_calls or set()
        contradict_unclear_on_calls = contradict_unclear_on_calls or set()

        async def fake_segment(current_state: ContractState) -> ContractState:
            calls.append("segment")
            return {
                **current_state,
                "clauses": deepcopy(segmented_clauses),
                "llm_metadata": {"segment": {"chunk_count": 1}},
            }

        async def fake_evaluate(current_state: ContractState) -> ContractState:
            calls.append("evaluate")
            counters["evaluate"] += 1
            low_confidence = counters["evaluate"] in evaluate_low_confidence_on_calls
            evaluated_type = "Other" if low_confidence else "Notice_Period"
            return {
                **current_state,
                "clauses": [
                    {
                        **clause,
                        "clause_type": evaluated_type,
                        "risk_score": 1 if low_confidence else 3,
                        "risk_reasoning": (
                            "Retry needed." if low_confidence else "Confident result."
                        ),
                    }
                    for clause in current_state["clauses"]
                ],
                "llm_metadata": {
                    **current_state.get("llm_metadata", {}),
                    "evaluate": {"low_confidence": low_confidence},
                },
            }

        async def fake_contradict(current_state: ContractState) -> ContractState:
            calls.append("contradict")
            counters["contradict"] += 1
            unclear = counters["contradict"] in contradict_unclear_on_calls
            return {
                **current_state,
                "contradictions": ["Clauses may conflict."] if unclear else [],
                "llm_metadata": {
                    **current_state.get("llm_metadata", {}),
                    "contradict": {"unclear": unclear},
                },
            }

        async def fake_report(current_state: ContractState) -> ContractState:
            calls.append("report")
            return {**current_state, "final_report": "# Executive summary"}

        monkeypatch.setattr(
            agent_controller,
            "STEP_HANDLERS",
            {
                "segment": fake_segment,
                "evaluate": fake_evaluate,
                "contradict": fake_contradict,
                "report": fake_report,
            },
        )

        result = await agent_controller.run_agent_controller(deepcopy(state))
        return result, calls, counters

    return _run


def test_build_plan_with_empty_state():
    plan = agent_controller.build_plan({})

    assert plan == ["segment", "evaluate", "contradict", "report"]


def test_build_plan_with_pre_evaluated_clauses():
    plan = agent_controller.build_plan(
        {
            "clauses": [
                {
                    "clause_id": 1,
                    "heading": "Notice",
                    "raw_text": "30 days notice",
                    "clause_type": "Notice_Period",
                    "risk_score": 2,
                    "risk_reasoning": "Within a common range.",
                },
                {
                    "clause_id": 2,
                    "heading": "Liability",
                    "raw_text": "Unlimited liability",
                    "clause_type": "Liability",
                    "risk_score": 5,
                    "risk_reasoning": "Unlimited personal liability is high risk.",
                },
            ]
        }
    )

    assert plan == ["contradict", "report"]


@pytest.mark.asyncio
async def test_contradict_step_is_skipped_when_clause_count_is_below_two(
    base_state: ContractState,
    run_controller: Callable[..., tuple[ContractState, list[str], dict[str, int]]],
):
    result, calls, _ = await run_controller(
        base_state,
        segmented_clauses=[
            {"clause_id": 1, "heading": "Notice", "raw_text": "30 days notice"},
        ],
    )

    skipped_logs = [log for log in result["step_logs"] if log["status"] == "skipped"]

    assert calls == ["segment", "evaluate", "report"]
    assert skipped_logs == [
        {
            "step": "contradict",
            "status": "skipped",
            "detail": "Skipped because there are too few clauses.",
        }
    ]


@pytest.mark.asyncio
async def test_controller_retries_evaluate_once_when_low_confidence(
    base_state: ContractState,
    clause_pair: list[dict],
    run_controller: Callable[..., tuple[ContractState, list[str], dict[str, int]]],
):
    result, calls, counters = await run_controller(
        base_state,
        segmented_clauses=clause_pair,
        evaluate_low_confidence_on_calls={1},
    )

    retry_logs = [log for log in result["step_logs"] if log["status"] == "retry"]

    assert calls == ["segment", "evaluate", "evaluate", "contradict", "report"]
    assert counters["evaluate"] == 2
    assert result["retry_counts"] == {"evaluate": 1}
    assert retry_logs == [
        {
            "step": "evaluate",
            "status": "retry",
            "detail": "Retrying evaluate once because quality heuristics flagged the result.",
        }
    ]


@pytest.mark.asyncio
async def test_controller_retries_contradict_once_when_analysis_is_unclear(
    base_state: ContractState,
    clause_pair: list[dict],
    run_controller: Callable[..., tuple[ContractState, list[str], dict[str, int]]],
):
    result, calls, counters = await run_controller(
        base_state,
        segmented_clauses=clause_pair,
        contradict_unclear_on_calls={1},
    )

    retry_logs = [log for log in result["step_logs"] if log["status"] == "retry"]

    assert calls == ["segment", "evaluate", "contradict", "contradict", "report"]
    assert counters["contradict"] == 2
    assert result["retry_counts"] == {"contradict": 1}
    assert retry_logs == [
        {
            "step": "contradict",
            "status": "retry",
            "detail": "Retrying contradict once because quality heuristics flagged the result.",
        }
    ]


@pytest.mark.asyncio
async def test_step_logs_are_created_in_execution_order(
    base_state: ContractState,
    clause_pair: list[dict],
    run_controller: Callable[..., tuple[ContractState, list[str], dict[str, int]]],
):
    result, calls, _ = await run_controller(base_state, segmented_clauses=clause_pair)

    completed_steps = [log["step"] for log in result["step_logs"] if log["status"] == "completed"]

    assert calls == ["segment", "evaluate", "contradict", "report"]
    assert result["plan"] == ["segment", "evaluate", "contradict", "report"]
    assert completed_steps == ["segment", "evaluate", "contradict", "report"]
    assert result["step_logs"]


@pytest.mark.asyncio
async def test_retry_counts_track_multiple_step_retries(
    base_state: ContractState,
    clause_pair: list[dict],
    run_controller: Callable[..., tuple[ContractState, list[str], dict[str, int]]],
):
    result, calls, counters = await run_controller(
        base_state,
        segmented_clauses=clause_pair,
        evaluate_low_confidence_on_calls={1},
        contradict_unclear_on_calls={1},
    )

    assert calls == [
        "segment",
        "evaluate",
        "evaluate",
        "contradict",
        "contradict",
        "report",
    ]
    assert counters == {"evaluate": 2, "contradict": 2}
    assert result["retry_counts"] == {"evaluate": 1, "contradict": 1}
