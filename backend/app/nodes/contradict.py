from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate

from app.core.llm import get_llm, invoke_json_llm
from app.core.logging_utils import get_logger
from app.prompts.contradict import CONTRADICT_PROMPT_MESSAGES
from app.schemas.contradict import ContradictOutput
from app.state import ContractState

logger = get_logger(__name__)

CONTRADICT_PROMPT = ChatPromptTemplate.from_messages(CONTRADICT_PROMPT_MESSAGES)


def _serialize_clauses(state: ContractState) -> str:
    payload = [
        {
            "clause_id": clause.get("clause_id"),
            "heading": clause.get("heading"),
            "raw_text": clause.get("raw_text"),
            "clause_type": clause.get("clause_type"),
            "risk_score": clause.get("risk_score"),
            "risk_reasoning": clause.get("risk_reasoning"),
        }
        for clause in state.get("clauses", [])
    ]
    return json.dumps(payload, ensure_ascii=True)


async def contradict_node(state: ContractState) -> ContractState:
    clauses = state.get("clauses", [])
    if not clauses:
        logger.info("contradict_node: no clauses to compare")
        return {
            **state,
            "contradictions": [],
            "llm_metadata": {**state.get("llm_metadata", {}), "contradict": {"clause_count": 0}},
        }

    logger.info("contradict_node: analyzing clauses=%s", len(clauses))
    llm = get_llm(temperature=0)
    result, llm_metadata = await invoke_json_llm(
        llm,
        CONTRADICT_PROMPT,
        {"clauses_json": _serialize_clauses(state)},
        ContradictOutput,
    )
    result = result or ContradictOutput(contradictions=[])

    logger.info(
        "contradict_node: completed contradictions=%s total_tokens=%s",
        len(result.contradictions),
        llm_metadata.get("usage_total_tokens", "unknown"),
    )
    return {
        **state,
        "contradictions": result.contradictions,
        "llm_metadata": {
            **state.get("llm_metadata", {}),
            "contradict": {
                "clause_count": len(clauses),
                "contradiction_count": len(result.contradictions),
                **llm_metadata,
            },
        },
    }
