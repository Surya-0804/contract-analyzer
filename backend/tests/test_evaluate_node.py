from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy

import pytest

from app.core.llm import LLMResponseError
from app.nodes import evaluate
from app.schemas.evaluate import EvaluatedClause, EvaluateOutput
from app.state import ContractState
from app.utils.knowledge_base import BASELINES


@pytest.fixture
def base_state() -> ContractState:
    return {
        "clauses": [],
        "contradictions": [],
        "final_report": "",
        "llm_metadata": {},
    }


@pytest.fixture
def sample_clauses() -> list[dict]:
    return [
        {
            "clause_id": 1,
            "heading": "Notice Period",
            "raw_text": "30 days notice",
        },
        {
            "clause_id": 2,
            "heading": "Liability",
            "raw_text": "Unlimited liability for employee.",
        },
    ]


@pytest.fixture
def run_evaluate(monkeypatch) -> Callable[..., tuple[ContractState, list[dict]]]:
    async def _run(
        state: ContractState,
        response: tuple[EvaluateOutput | None, dict] | Exception,
    ) -> tuple[ContractState, list[dict]]:
        llm = object()
        payloads: list[dict] = []

        monkeypatch.setattr(evaluate, "get_llm", lambda temperature=0: llm)

        async def fake_invoke_json_llm(current_llm, prompt, payload, output_model):
            assert current_llm is llm
            assert output_model is EvaluateOutput
            payloads.append(payload)
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(evaluate, "invoke_json_llm", fake_invoke_json_llm)
        result = await evaluate.evaluate_node(deepcopy(state))
        return result, payloads

    return _run


def _evaluated_clause(
    clause_id: int,
    clause_type: str,
    risk_score: int,
    risk_reasoning: str,
) -> EvaluatedClause:
    return EvaluatedClause(
        clause_id=clause_id,
        clause_type=clause_type,
        risk_score=risk_score,
        risk_reasoning=risk_reasoning,
    )


@pytest.mark.asyncio
async def test_enriches_clauses_and_preserves_existing_fields(
    base_state: ContractState,
    sample_clauses: list[dict],
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(sample_clauses)}

    result, payloads = await run_evaluate(
        state,
        (
            EvaluateOutput(
                clauses=[
                    _evaluated_clause(
                        1,
                        "Notice_Period",
                        2,
                        "The notice period is within a common range.",
                    ),
                    _evaluated_clause(
                        2,
                        "Liability",
                        5,
                        "Unlimited liability is high risk.",
                    ),
                ]
            ),
            {"usage_input_tokens": 12, "usage_output_tokens": 4, "usage_total_tokens": 16},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == sample_clauses
    assert json.loads(payloads[0]["baselines"]) == BASELINES
    assert result["clauses"] == [
        {
            "clause_id": 1,
            "heading": "Notice Period",
            "raw_text": "30 days notice",
            "clause_type": "Notice_Period",
            "risk_score": 2,
            "risk_reasoning": "The notice period is within a common range.",
        },
        {
            "clause_id": 2,
            "heading": "Liability",
            "raw_text": "Unlimited liability for employee.",
            "clause_type": "Liability",
            "risk_score": 5,
            "risk_reasoning": "Unlimited liability is high risk.",
        },
    ]
    assert result["llm_metadata"]["evaluate"] == {
        "clause_count": 2,
        "fallback_count": 0,
        "other_count": 0,
        "low_confidence": False,
        "usage_input_tokens": 12,
        "usage_output_tokens": 4,
        "usage_total_tokens": 16,
    }


@pytest.mark.asyncio
async def test_processes_small_and_large_clause_text_without_modifying_raw_text(
    base_state: ContractState,
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    large_text = "pay " * 2000
    state = {
        **base_state,
        "clauses": [
            {"clause_id": 1, "heading": "Short", "raw_text": "x"},
            {"clause_id": 2, "heading": "Large", "raw_text": large_text},
        ],
    }

    result, payloads = await run_evaluate(
        state,
        (
            EvaluateOutput(
                clauses=[
                    _evaluated_clause(1, "Other", 1, "Very short clause."),
                    _evaluated_clause(
                        2,
                        "Compensation",
                        4,
                        "Large compensation clause with elevated risk.",
                    ),
                ]
            ),
            {"usage_total_tokens": 21},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == state["clauses"]
    assert result["clauses"][0]["raw_text"] == "x"
    assert result["clauses"][1]["raw_text"] == large_text
    assert result["clauses"][1]["clause_type"] == "Compensation"


@pytest.mark.asyncio
async def test_returns_early_for_empty_clause_list_without_invoking_llm(
    base_state: ContractState,
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    result, payloads = await run_evaluate(
        base_state,
        (
            EvaluateOutput(clauses=[]),
            {"usage_input_tokens": 1, "usage_output_tokens": 1, "usage_total_tokens": 2},
        ),
    )

    assert payloads == []
    assert result["clauses"] == []
    assert result["llm_metadata"]["evaluate"] == {"clause_count": 0}


@pytest.mark.asyncio
async def test_propagates_invalid_llm_json_response(
    base_state: ContractState,
    sample_clauses: list[dict],
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(sample_clauses)}

    with pytest.raises(LLMResponseError, match="invalid JSON"):
        await run_evaluate(state, LLMResponseError("LLM returned invalid JSON"))


@pytest.mark.asyncio
async def test_marks_result_low_confidence_when_a_clause_is_missing_from_llm_output(
    base_state: ContractState,
    sample_clauses: list[dict],
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(sample_clauses)}

    result, _ = await run_evaluate(
        state,
        (
            EvaluateOutput(
                clauses=[
                    _evaluated_clause(1, "Notice_Period", 2, "Reasonable notice clause."),
                ]
            ),
            {"usage_total_tokens": 9},
        ),
    )

    assert result["clauses"][0]["clause_type"] == "Notice_Period"
    assert result["clauses"][1] == {
        "clause_id": 2,
        "heading": "Liability",
        "raw_text": "Unlimited liability for employee.",
        "clause_type": "Other",
        "risk_score": 1,
        "risk_reasoning": "No evaluation returned for this clause.",
    }
    assert result["llm_metadata"]["evaluate"]["fallback_count"] == 1
    assert result["llm_metadata"]["evaluate"]["other_count"] == 1
    assert result["llm_metadata"]["evaluate"]["low_confidence"] is True


@pytest.mark.asyncio
async def test_marks_result_low_confidence_when_all_classifications_are_other(
    base_state: ContractState,
    sample_clauses: list[dict],
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {**base_state, "clauses": deepcopy(sample_clauses)}

    result, _ = await run_evaluate(
        state,
        (
            EvaluateOutput(
                clauses=[
                    _evaluated_clause(1, "Other", 1, "No matching category."),
                    _evaluated_clause(2, "Other", 1, "No matching category."),
                ]
            ),
            {"usage_total_tokens": 8},
        ),
    )

    assert [clause["clause_type"] for clause in result["clauses"]] == ["Other", "Other"]
    assert result["llm_metadata"]["evaluate"]["fallback_count"] == 0
    assert result["llm_metadata"]["evaluate"]["other_count"] == 2
    assert result["llm_metadata"]["evaluate"]["low_confidence"] is True


@pytest.mark.asyncio
async def test_raises_before_llm_call_when_clause_input_is_missing_required_fields(
    base_state: ContractState,
    run_evaluate: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": [
            {
                "clause_id": 1,
                "raw_text": "30 days notice",
            }
        ],
    }

    with pytest.raises(KeyError, match="heading"):
        await run_evaluate(
            state,
            (
                EvaluateOutput(clauses=[]),
                {"usage_total_tokens": 0},
            ),
        )
