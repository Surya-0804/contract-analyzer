from __future__ import annotations

import asyncio
from typing import List

import tiktoken
from langchain_core.prompts import ChatPromptTemplate

from app.core.llm import estimate_tokens, get_llm, invoke_json_llm
from app.core.logging_utils import get_logger
from app.core.settings import get_settings
from app.prompts.segment import SEGMENT_PROMPT_MESSAGES
from app.schemas.segment import SegmentOutput
from app.state import Clause, ContractState

logger = get_logger(__name__)


# ── Prompt ─────────────────────────────────────────────────────────
SEGMENT_PROMPT = ChatPromptTemplate.from_messages(SEGMENT_PROMPT_MESSAGES)


def chunk_text(text: str, model: str, max_tokens: int = 3000, overlap: int = 200) -> List[str]:
    if not text:
        return []

    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return [text]

    chunks: List[str] = []
    step = max_tokens - overlap
    for start in range(0, len(tokens), step):
        end = min(start + max_tokens, len(tokens))
        chunk = encoding.decode(tokens[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(tokens):
            break
    return chunks


def normalize_clause_text(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def deduplicate_clauses(clauses: List[Clause]) -> List[Clause]:
    deduped: List[Clause] = []
    seen: set[str] = set()

    for clause in clauses:
        normalized = normalize_clause_text(clause["raw_text"])
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(clause)

    for idx, clause in enumerate(deduped, start=1):
        clause["clause_id"] = idx
    return deduped


# ── Node function ───────────────────────────────────────────────────
async def segment_node(state: ContractState) -> ContractState:
    logger.info("segment_node: starting clause extraction")

    settings = get_settings()
    formatted_messages = SEGMENT_PROMPT.format_messages(contract_text=state["raw_pdf_text"])
    prompt_text = "\n".join(str(message.content) for message in formatted_messages)
    estimated_input_tokens = estimate_tokens(prompt_text, settings.openrouter_model)
    document_tokens = estimate_tokens(state["raw_pdf_text"], settings.openrouter_model)
    document_metadata = state.get("document_metadata", {})

    logger.info(
        "segment_node: prepared prompt pages=%s chars=%s doc_tokens_est=%s prompt_tokens_est=%s",
        document_metadata.get("page_count", "unknown"),
        len(state["raw_pdf_text"]),
        document_tokens,
        estimated_input_tokens,
    )
    if estimated_input_tokens >= settings.llm_warn_input_tokens:
        logger.warning(
            "segment_node: large prompt prompt_tokens_est=%s warn_threshold=%s",
            estimated_input_tokens,
            settings.llm_warn_input_tokens,
        )

    llm = get_llm(temperature=0)
    chunks = chunk_text(
        state["raw_pdf_text"],
        settings.openrouter_model,
        max_tokens=settings.segment_chunk_max_tokens,
        overlap=settings.segment_chunk_overlap_tokens,
    )
    logger.info(
        (
            "segment_node: chunked document chunk_count=%s chunk_max_tokens=%s "
            "overlap_tokens=%s delay_seconds=%s"
        ),
        len(chunks),
        settings.segment_chunk_max_tokens,
        settings.segment_chunk_overlap_tokens,
        settings.segment_chunk_delay_seconds,
    )

    all_clauses: List[Clause] = []
    aggregated_metadata = {
        "chunk_count": len(chunks),
        "usage_input_tokens": 0,
        "usage_output_tokens": 0,
        "usage_total_tokens": 0,
    }

    for index, chunk in enumerate(chunks, start=1):
        chunk_tokens = estimate_tokens(chunk, settings.openrouter_model)
        logger.info(
            "segment_node: invoking structured LLM chunk=%s/%s chunk_tokens_est=%s",
            index,
            len(chunks),
            chunk_tokens,
        )
        result, llm_metadata = await invoke_json_llm(
            llm,
            SEGMENT_PROMPT,
            {"contract_text": chunk},
            SegmentOutput,
        )
        result = result or SegmentOutput(clauses=[])

        aggregated_metadata["usage_input_tokens"] += llm_metadata.get("usage_input_tokens", 0) or 0
        aggregated_metadata["usage_output_tokens"] += (
            llm_metadata.get("usage_output_tokens", 0) or 0
        )
        aggregated_metadata["usage_total_tokens"] += llm_metadata.get("usage_total_tokens", 0) or 0

        for clause in result.clauses:
            all_clauses.append(
                {
                    "clause_id": clause.clause_id,
                    "heading": clause.heading,
                    "raw_text": clause.raw_text,
                }
            )

        if index < len(chunks) and settings.segment_chunk_delay_seconds > 0:
            logger.info(
                "segment_node: sleeping before next chunk delay_seconds=%s next_chunk=%s/%s",
                settings.segment_chunk_delay_seconds,
                index + 1,
                len(chunks),
            )
            await asyncio.sleep(settings.segment_chunk_delay_seconds)

    clauses = deduplicate_clauses(all_clauses)

    logger.info(
        "segment_node: extracted clauses=%s output_tokens=%s total_tokens=%s",
        len(clauses),
        aggregated_metadata.get("usage_output_tokens", "unknown"),
        aggregated_metadata.get("usage_total_tokens", "unknown"),
    )
    return {
        **state,
        "clauses": clauses,
        "llm_metadata": {"segment": aggregated_metadata},
    }
