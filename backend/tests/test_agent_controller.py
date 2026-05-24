from __future__ import annotations

import pytest

from app.nodes import agent_controller
from app.state import ContractState


def test_build_plan_includes_full_analysis_flow_for_fresh_state():
    state: ContractState = {
        "raw_pdf_text": "contract text",
        "clauses": [],
        "contradictions": [],
        "final_report": "",
    }

    assert agent_controller.build_plan(state) == [
        "segment",
        "evaluate",
        "contradict",
        "report",
    ]


@pytest.mark.asyncio
async def test_controller_skips_contradict_when_too_few_clauses(monkeypatch):
    async def fake_segment(state: ContractState) -> ContractState:
        return {
            **state,
            "clauses": [
                {"clause_id": 1, "heading": "Notice", "raw_text": "30 days notice"},
            ],
            "llm_metadata": {"segment": {"chunk_count": 1}},
        }

    async def fake_evaluate(state: ContractState) -> ContractState:
        return {
            **state,
            "clauses": [
                {
                    **state["clauses"][0],
                    "clause_type": "Notice_Period",
                    "risk_score": 2,
                    "risk_reasoning": "Common notice range.",
                }
            ],
            "llm_metadata": {
                **state.get("llm_metadata", {}),
                "evaluate": {"low_confidence": False},
            },
        }

    async def fake_contradict(state: ContractState) -> ContractState:
        raise AssertionError("contradict should be skipped for a single clause")

    async def fake_report(state: ContractState) -> ContractState:
        return {**state, "final_report": "# Executive summary"}

    monkeypatch.setattr(agent_controller, "segment_node", fake_segment)
    monkeypatch.setattr(agent_controller, "evaluate_node", fake_evaluate)
    monkeypatch.setattr(agent_controller, "contradict_node", fake_contradict)
    monkeypatch.setattr(agent_controller, "report_node", fake_report)
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

    state: ContractState = {
        "goal": "analyze contract",
        "raw_pdf_text": "contract text",
        "clauses": [],
        "contradictions": [],
        "final_report": "",
        "step_logs": [],
        "retry_counts": {},
    }

    result = await agent_controller.run_agent_controller(state)

    assert result["final_report"] == "# Executive summary"
    assert any(
        log["step"] == "contradict" and log["status"] == "skipped"
        for log in result["step_logs"]
    )


@pytest.mark.asyncio
async def test_controller_retries_evaluate_once_when_low_confidence(monkeypatch):
    calls = {"evaluate": 0, "contradict": 0}

    async def fake_segment(state: ContractState) -> ContractState:
        return {
            **state,
            "clauses": [
                {"clause_id": 1, "heading": "Notice", "raw_text": "30 days notice"},
                {"clause_id": 2, "heading": "Liability", "raw_text": "Unlimited liability"},
            ],
            "llm_metadata": {"segment": {"chunk_count": 1}},
        }

    async def fake_evaluate(state: ContractState) -> ContractState:
        calls["evaluate"] += 1
        low_confidence = calls["evaluate"] == 1
        return {
            **state,
            "clauses": [
                {
                    **clause,
                    "clause_type": "Other" if low_confidence else "Notice_Period",
                    "risk_score": 1 if low_confidence else 3,
                    "risk_reasoning": "Retry needed." if low_confidence else "Confident result.",
                }
                for clause in state["clauses"]
            ],
            "llm_metadata": {
                **state.get("llm_metadata", {}),
                "evaluate": {"low_confidence": low_confidence},
            },
        }

    async def fake_contradict(state: ContractState) -> ContractState:
        calls["contradict"] += 1
        return {
            **state,
            "contradictions": [],
            "llm_metadata": {
                **state.get("llm_metadata", {}),
                "contradict": {"unclear": False},
            },
        }

    async def fake_report(state: ContractState) -> ContractState:
        return {**state, "final_report": "# Executive summary"}

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

    state: ContractState = {
        "goal": "analyze contract",
        "raw_pdf_text": "contract text",
        "clauses": [],
        "contradictions": [],
        "final_report": "",
        "step_logs": [],
        "retry_counts": {},
    }

    result = await agent_controller.run_agent_controller(state)

    assert calls["evaluate"] == 2
    assert result["retry_counts"]["evaluate"] == 1
    assert any(log["status"] == "retry" and log["step"] == "evaluate" for log in result["step_logs"])
