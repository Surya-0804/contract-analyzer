from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate

from app.core.llm import get_llm, invoke_json_llm
from app.core.logging_utils import get_logger
from app.prompts.report import REPORT_PROMPT_MESSAGES
from app.schemas.report import ReportOutput
from app.state import ContractState

logger = get_logger(__name__)

REPORT_PROMPT = ChatPromptTemplate.from_messages(REPORT_PROMPT_MESSAGES)


def _serialize_clauses(state: ContractState) -> str:
    return json.dumps(state.get("clauses", []), ensure_ascii=True)


def _serialize_contradictions(state: ContractState) -> str:
    return json.dumps(state.get("contradictions", []), ensure_ascii=True)


async def report_node(state: ContractState) -> ContractState:
    logger.info(
        "report_node: generating report clauses=%s contradictions=%s",
        len(state.get("clauses", [])),
        len(state.get("contradictions", [])),
    )
    llm = get_llm(temperature=0)
    result, llm_metadata = await invoke_json_llm(
        llm,
        REPORT_PROMPT,
        {
            "clauses_json": _serialize_clauses(state),
            "contradictions_json": _serialize_contradictions(state),
        },
        ReportOutput,
    )
    result = result or ReportOutput(final_report="")

    logger.info(
        "report_node: completed report_chars=%s total_tokens=%s",
        len(result.final_report),
        llm_metadata.get("usage_total_tokens", "unknown"),
    )
    return {
        **state,
        "final_report": result.final_report,
        "llm_metadata": {
            **state.get("llm_metadata", {}),
            "report": {"report_chars": len(result.final_report), **llm_metadata},
        },
    }
