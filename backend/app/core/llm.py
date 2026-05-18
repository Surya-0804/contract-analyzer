from __future__ import annotations

import time
from typing import Type

from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from app.core.logging_utils import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)


def get_llm(model: str | None = None, temperature: float = 0.0, **kwargs) -> ChatOpenAI:
    """Create and return a configured ChatOpenAI instance.

    Centralizes LLM instantiation so model/temperature defaults live in one place.
    """
    try:
        settings = get_settings()
        resolved_model = model or settings.openrouter_model
        logger.info(
            "constructing ChatOpenAI client for model=%s base_url=%s timeout=%ss retries=%s",
            resolved_model,
            settings.openai_api_base or "<default>",
            settings.openai_timeout_seconds,
            settings.openai_max_retries,
        )
        llm = ChatOpenAI(
            model=resolved_model,
            temperature=temperature,
            api_key=settings.openai_api_key or None,
            base_url=settings.openai_api_base or None,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
            **kwargs,
        )
        return llm
    except Exception as exc:
        logger.error("failed to construct ChatOpenAI: %s", exc, exc_info=True)
        raise


def get_structured_llm(
    output_model: Type[BaseModel],
    model: str | None = None,
    temperature: float = 0.0,
    **kwargs,
):
    """Return an LLM instance configured for structured output.

    This calls `with_structured_output(output_model)` on the underlying LLM
    and surfaces errors clearly.
    """
    llm = get_llm(model=model, temperature=temperature, **kwargs)
    try:
        structured = llm.with_structured_output(output_model)
        return structured
    except Exception as exc:
        logger.error("LLM does not support structured output: %s", exc, exc_info=True)
        raise


async def invoke_structured_llm(chain, payload: dict):
    started = time.perf_counter()
    try:
        result = await chain.ainvoke(payload)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.error("structured LLM call failed after %.2fs: %s", elapsed, exc, exc_info=True)
        raise

    elapsed = time.perf_counter() - started
    logger.info("structured LLM call completed in %.2fs", elapsed)
    return result
