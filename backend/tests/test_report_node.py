from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy

import pytest

from app.core.llm import LLMResponseError
from app.nodes import report
from app.schemas.report import ReportOutput
from app.state import ContractState


@pytest.fixture
def base_state() -> ContractState:
    return {
        "clauses": [],
        "contradictions": [],
        "final_report": "",
        "llm_metadata": {},
    }


@pytest.fixture
def evaluated_clauses() -> list[dict]:
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
            "heading": "Liability",
            "raw_text": "The employee accepts unlimited liability.",
            "clause_type": "Liability",
            "risk_score": 5,
            "risk_reasoning": "Unlimited liability is high risk.",
        },
    ]


@pytest.fixture
def run_report(monkeypatch) -> Callable[..., tuple[ContractState, list[dict]]]:
    async def _run(
        state: ContractState,
        response: tuple[ReportOutput | None, dict] | Exception,
    ) -> tuple[ContractState, list[dict]]:
        llm = object()
        payloads: list[dict] = []

        monkeypatch.setattr(report, "get_llm", lambda temperature=0: llm)

        async def fake_invoke_json_llm(current_llm, prompt, payload, output_model):
            assert current_llm is llm
            assert output_model is ReportOutput
            payloads.append(payload)
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(report, "invoke_json_llm", fake_invoke_json_llm)
        result = await report.report_node(deepcopy(state))
        return result, payloads

    return _run


def _sample_report_markdown(*, contradiction_line: str) -> str:
    return "\n".join(
        [
            "# Executive summary",
            "Contract review completed.",
            "",
            "## High-risk clauses",
            "- Clause 2: liability risk is high.",
            "",
            "## Contradictions",
            contradiction_line,
            "",
            "## Safe clauses",
            "- Clause 1: notice period is acceptable.",
            "",
            "## Disclaimer",
            "This is not legal advice.",
        ]
    )


def _assert_has_report_sections(markdown: str) -> None:
    assert isinstance(markdown, str)
    assert markdown.strip()
    assert "# Executive summary" in markdown
    assert "## High-risk clauses" in markdown
    assert "## Contradictions" in markdown
    assert "## Safe clauses" in markdown
    assert "## Disclaimer" in markdown


@pytest.mark.asyncio
async def test_stores_generated_report_in_state_and_includes_expected_sections(
    base_state: ContractState,
    evaluated_clauses: list[dict],
    run_report: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": deepcopy(evaluated_clauses),
        "contradictions": ["Clause 1 conflicts with Clause 2 on notice obligations."],
    }
    report_markdown = _sample_report_markdown(
        contradiction_line="- Clause 1 conflicts with Clause 2 on notice obligations."
    )

    result, payloads = await run_report(
        state,
        (
            ReportOutput(final_report=report_markdown),
            {"usage_input_tokens": 14, "usage_output_tokens": 7, "usage_total_tokens": 21},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == evaluated_clauses
    assert json.loads(payloads[0]["contradictions_json"]) == state["contradictions"]
    assert result["final_report"].startswith("# Executive summary")
    assert "Clause 1 conflicts with Clause 2" in result["final_report"]
    _assert_has_report_sections(result["final_report"])
    assert result["llm_metadata"]["report"]["report_chars"] == len(report_markdown)
    assert result["llm_metadata"]["report"]["usage_total_tokens"] == 21


@pytest.mark.asyncio
async def test_empty_clauses_can_still_produce_valid_minimal_report(
    base_state: ContractState,
    run_report: Callable[..., tuple[ContractState, list[dict]]],
):
    minimal_report = "\n".join(
        [
            "# Executive summary",
            "No clauses were available for analysis.",
            "",
            "## High-risk clauses",
            "None identified.",
            "",
            "## Contradictions",
            "No contradictions found.",
            "",
            "## Safe clauses",
            "None identified.",
            "",
            "## Disclaimer",
            "This is not legal advice.",
        ]
    )

    result, payloads = await run_report(
        base_state,
        (
            ReportOutput(final_report=minimal_report),
            {"usage_total_tokens": 9},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["clauses_json"]) == []
    assert json.loads(payloads[0]["contradictions_json"]) == []
    _assert_has_report_sections(result["final_report"])


@pytest.mark.asyncio
async def test_report_mentions_absence_of_contradictions_when_none_are_present(
    base_state: ContractState,
    evaluated_clauses: list[dict],
    run_report: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": deepcopy(evaluated_clauses),
        "contradictions": [],
    }
    report_markdown = _sample_report_markdown(contradiction_line="No contradictions found.")

    result, payloads = await run_report(
        state,
        (
            ReportOutput(final_report=report_markdown),
            {"usage_total_tokens": 12},
        ),
    )

    assert len(payloads) == 1
    assert json.loads(payloads[0]["contradictions_json"]) == []
    _assert_has_report_sections(result["final_report"])
    assert "No contradictions found." in result["final_report"]


@pytest.mark.asyncio
async def test_report_handles_large_clause_sets_without_changing_payload_shape(
    base_state: ContractState,
    run_report: Callable[..., tuple[ContractState, list[dict]]],
):
    clauses = [
        {
            "clause_id": index,
            "heading": f"Clause {index}",
            "raw_text": f"Clause text {index}",
            "clause_type": "Other",
            "risk_score": 1,
            "risk_reasoning": "Low risk.",
        }
        for index in range(1, 51)
    ]
    state = {
        **base_state,
        "clauses": clauses,
        "contradictions": [],
    }
    report_markdown = _sample_report_markdown(contradiction_line="No contradictions found.")

    result, payloads = await run_report(
        state,
        (
            ReportOutput(final_report=report_markdown),
            {"usage_total_tokens": 30},
        ),
    )

    assert len(payloads) == 1
    assert len(json.loads(payloads[0]["clauses_json"])) == 50
    assert json.loads(payloads[0]["contradictions_json"]) == []
    _assert_has_report_sections(result["final_report"])


@pytest.mark.asyncio
async def test_propagates_malformed_llm_output(
    base_state: ContractState,
    evaluated_clauses: list[dict],
    run_report: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": deepcopy(evaluated_clauses),
        "contradictions": [],
    }

    with pytest.raises(LLMResponseError, match="invalid JSON"):
        await run_report(state, LLMResponseError("LLM returned invalid JSON"))


@pytest.mark.asyncio
async def test_empty_llm_result_defaults_to_empty_report_string(
    base_state: ContractState,
    evaluated_clauses: list[dict],
    run_report: Callable[..., tuple[ContractState, list[dict]]],
):
    state = {
        **base_state,
        "clauses": deepcopy(evaluated_clauses),
        "contradictions": ["Clause 1 conflicts with Clause 2."],
    }

    result, _ = await run_report(
        state,
        (
            None,
            {"usage_total_tokens": 5},
        ),
    )

    assert result["final_report"] == ""
    assert result["llm_metadata"]["report"] == {
        "report_chars": 0,
        "usage_total_tokens": 5,
    }
