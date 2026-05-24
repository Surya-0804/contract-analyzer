from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy

import pytest

from app.core.llm import LLMResponseError
from app.nodes import contradict
from app.schemas.contradict import ContradictOutput
from app.state import ContractState


@pytest.fixture
def base_state() -> ContractState:
    return {
        "clauses": [],
        "contradictions": ["stale contradiction"],
        "final_report": "",
        "llm_metadata": {},
    }


@pytest.fixture
def conflicting_clauses() -> list[dict]:
    return [
        {
            "clause_id": 1,
            "heading": "Notice Period",
            "raw_text": "The employee must give 30 days notice.",
            "clause_type": "Notice_Period",
            "risk_score": 2,
            "risk_reasoning": "Standard notice range.",
        },
        {
            "clause_id": 2,
            "heading": "Notice Period Override",
            "raw_text": "The employee must give 60 days notice.",
            "clause_type": "Notice_Period",
            "risk_score": 3,
            "risk_reasoning": "Longer than usual notice range.",
        },
    ]


@pytest.fixture
def run_contradict(monkeypatch) -> Callable[..., tuple[ContractState, list[dict]]]:
    async def _run(
        state: ContractState,
        response: tuple[ContradictOutput | None, dict] | Exception,
    ) -> tuple[ContractState, list[dict]]:
        llm = object()
        payloads: list[dict] = []

        monkeypatch.setattr(contradict, "get_llm", lambda temperature=0: llm)

        async def fake_invoke_json_llm(current_llm, prompt, payload, output_model):
            assert current_llm is llm
            assert output_model is ContradictOutput
            payloads.append(payload)
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(contradict, "invoke_json_llm", fake_invoke_json_llm)
        result = await contradict.contradict_node(deepcopy(state))
        return result, payloads

    return _run


@pytest.mark.asyncio
async def test_replaces_existing_contradictions_with_llm_output(
    base_state: ContractState,
    conflicting_clauses: list[dict],
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(conflicting_clauses)}

    result, payloads = await run_contradict(
        state,
        (
            ContradictOutput(
                contradictions=[
                    "Clause 1 and Clause 2 state different notice periods.",
                ]
            ),
            {"usage_input_tokens": 10, "usage_output_tokens": 3, "usage_total_tokens": 13},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == conflicting_clauses
    assert result["contradictions"] == ["Clause 1 and Clause 2 state different notice periods."]
    assert result["llm_metadata"]["contradict"] == {
        "clause_count": 2,
        "contradiction_count": 1,
        "unclear": False,
        "usage_input_tokens": 10,
        "usage_output_tokens": 3,
        "usage_total_tokens": 13,
    }


@pytest.mark.asyncio
async def test_returns_empty_contradictions_without_invoking_llm_for_empty_clause_list(
    base_state: ContractState,
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    result, payloads = await run_contradict(
        {**base_state, "clauses": []},
        (
            ContradictOutput(contradictions=["should never be used"]),
            {"usage_total_tokens": 1},
        ),
    )

    assert payloads == []
    assert result["contradictions"] == []
    assert result["llm_metadata"]["contradict"] == {"clause_count": 0}


@pytest.mark.asyncio
async def test_single_clause_can_be_analyzed_without_reporting_contradictions(
    base_state: ContractState,
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": [
            {
                "clause_id": 1,
                "heading": "Notice Period",
                "raw_text": "The employee must give 30 days notice.",
                "clause_type": "Notice_Period",
                "risk_score": 2,
                "risk_reasoning": "Standard notice range.",
            }
        ],
    }

    result, payloads = await run_contradict(
        state,
        (
            ContradictOutput(contradictions=[]),
            {"usage_total_tokens": 4},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == state["clauses"]
    assert result["contradictions"] == []
    assert result["llm_metadata"]["contradict"] == {
        "clause_count": 1,
        "contradiction_count": 0,
        "unclear": False,
        "usage_total_tokens": 4,
    }


@pytest.mark.asyncio
async def test_preserves_contradiction_list_shape_for_multiple_conflicts(
    base_state: ContractState,
    conflicting_clauses: list[dict],
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(conflicting_clauses)}

    result, _ = await run_contradict(
        state,
        (
            ContradictOutput(
                contradictions=[
                    "Clause 1 requires 30 days notice while Clause 2 requires 60 days notice.",
                    "Clause 1 conflicts with Clause 2 on notice obligations.",
                ]
            ),
            {"usage_total_tokens": 15},
        ),
    )

    assert len(result["contradictions"]) == 2
    assert all(isinstance(item, str) and item for item in result["contradictions"])
    assert result["llm_metadata"]["contradict"]["contradiction_count"] == 2


@pytest.mark.asyncio
async def test_sets_unclear_flag_when_llm_uses_ambiguous_conflict_language(
    base_state: ContractState,
    conflicting_clauses: list[dict],
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(conflicting_clauses)}

    result, _ = await run_contradict(
        state,
        (
            ContradictOutput(
                contradictions=[
                    "Clause 1 may conflict with Clause 2 on notice requirements.",
                ]
            ),
            {"usage_total_tokens": 8},
        ),
    )

    assert result["contradictions"] == [
        "Clause 1 may conflict with Clause 2 on notice requirements."
    ]
    assert result["llm_metadata"]["contradict"]["unclear"] is True
    assert result["llm_metadata"]["contradict"]["contradiction_count"] == 1


@pytest.mark.asyncio
async def test_serializes_duplicate_and_partial_clause_data_without_failure(
    base_state: ContractState,
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": [
            {
                "clause_id": 1,
                "heading": "Notice Period",
                "raw_text": "30 days notice",
                "clause_type": "Notice_Period",
                "risk_score": 2,
                "risk_reasoning": "Standard.",
            },
            {
                "clause_id": 1,
                "heading": "Notice Period",
                "raw_text": "30 days notice",
            },
        ],
    }

    result, payloads = await run_contradict(
        state,
        (
            ContradictOutput(contradictions=[]),
            {"usage_total_tokens": 5},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == [
        {
            "clause_id": 1,
            "heading": "Notice Period",
            "raw_text": "30 days notice",
            "clause_type": "Notice_Period",
            "risk_score": 2,
            "risk_reasoning": "Standard.",
        },
        {
            "clause_id": 1,
            "heading": "Notice Period",
            "raw_text": "30 days notice",
            "clause_type": None,
            "risk_score": None,
            "risk_reasoning": None,
        },
    ]
    assert result["contradictions"] == []


@pytest.mark.asyncio
async def test_propagates_invalid_llm_json_response(
    base_state: ContractState,
    conflicting_clauses: list[dict],
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(conflicting_clauses)}

    with pytest.raises(LLMResponseError, match="invalid JSON"):
        await run_contradict(state, LLMResponseError("LLM returned invalid JSON"))


@pytest.mark.asyncio
async def test_treats_empty_llm_result_as_no_contradictions(
    base_state: ContractState,
    conflicting_clauses: list[dict],
    run_contradict: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(conflicting_clauses)}

    result, _ = await run_contradict(
        state,
        (
            None,
            {"usage_total_tokens": 6},
        ),
    )

    assert result["contradictions"] == []
    assert result["llm_metadata"]["contradict"] == {
        "clause_count": 2,
        "contradiction_count": 0,
        "unclear": False,
        "usage_total_tokens": 6,
    }
