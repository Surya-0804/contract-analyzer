from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate

from app.core.llm import get_llm, invoke_json_llm
from app.core.logging_utils import get_logger
from app.prompts.evaluate import EVALUATE_PROMPT_MESSAGES
from app.schemas.evaluate import EvaluateOutput
from app.state import Clause, ContractState
from app.utils.knowledge_base import BASELINES

logger = get_logger(__name__)

EVALUATE_PROMPT = ChatPromptTemplate.from_messages(EVALUATE_PROMPT_MESSAGES)


def _serialize_clauses(clauses: list[Clause]) -> str:
    payload = [
        {
            "clause_id": clause["clause_id"],
            "heading": clause["heading"],
            "raw_text": clause["raw_text"],
        }
        for clause in clauses
    ]
    return json.dumps(payload, ensure_ascii=True)


def _serialize_baselines() -> str:
    return json.dumps(BASELINES, ensure_ascii=True, indent=2)


async def evaluate_node(state: ContractState) -> ContractState:
    clauses = state.get("clauses", [])
    if not clauses:
        logger.info("evaluate_node: no clauses to evaluate")
        return {
            **state,
            "llm_metadata": {**state.get("llm_metadata", {}), "evaluate": {"clause_count": 0}},
        }

    logger.info("evaluate_node: evaluating clauses=%s", len(clauses))
    llm = get_llm(temperature=0)
    result, llm_metadata = await invoke_json_llm(
        llm,
        EVALUATE_PROMPT,
        {
            "baselines": _serialize_baselines(),
            "clauses_json": _serialize_clauses(clauses),
        },
        EvaluateOutput,
    )
    result = result or EvaluateOutput(clauses=[])

    evaluations = {item.clause_id: item for item in result.clauses}
    enriched_clauses: list[Clause] = []

    for clause in clauses:
        evaluated = evaluations.get(clause["clause_id"])
        enriched: Clause = dict(clause)
        if evaluated is not None:
            enriched["clause_type"] = evaluated.clause_type
            enriched["risk_score"] = evaluated.risk_score
            enriched["risk_reasoning"] = evaluated.risk_reasoning
        else:
            enriched["clause_type"] = "Other"
            enriched["risk_score"] = 1
            enriched["risk_reasoning"] = "No evaluation returned for this clause."
        enriched_clauses.append(enriched)

    logger.info(
        "evaluate_node: completed clauses=%s total_tokens=%s",
        len(enriched_clauses),
        llm_metadata.get("usage_total_tokens", "unknown"),
    )
    return {
        **state,
        "clauses": enriched_clauses,
        "llm_metadata": {
            **state.get("llm_metadata", {}),
            "evaluate": {"clause_count": len(enriched_clauses), **llm_metadata},
        },
    }
