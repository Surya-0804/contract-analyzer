from __future__ import annotations
from typing import List

from langchain_core.prompts import ChatPromptTemplate

from app.prompts.segment import SEGMENT_PROMPT_MESSAGES
from app.schemas.segment import SegmentOutput
from app.core.llm import get_structured_llm, invoke_structured_llm
from app.state import ContractState, Clause
from app.core.logging_utils import get_logger

logger = get_logger(__name__)


# ── Prompt ─────────────────────────────────────────────────────────
SEGMENT_PROMPT = ChatPromptTemplate.from_messages(SEGMENT_PROMPT_MESSAGES)


# ── Node function ───────────────────────────────────────────────────
async def segment_node(state: ContractState) -> ContractState:
    logger.info("segment_node: starting clause extraction")

    structured_llm = get_structured_llm(SegmentOutput, temperature=0)
    chain = SEGMENT_PROMPT | structured_llm

    logger.info("segment_node: invoking structured LLM")
    result: SegmentOutput = await invoke_structured_llm(
        chain,
        {"contract_text": state["raw_pdf_text"]},
    )

    clauses: List[Clause] = [
        {"clause_id": c.clause_id, "heading": c.heading, "raw_text": c.raw_text}
        for c in result.clauses
    ]

    logger.info(f"segment_node: extracted {len(clauses)} clauses")
    return {**state, "clauses": clauses}
