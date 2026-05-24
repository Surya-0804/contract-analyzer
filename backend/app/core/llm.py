from __future__ import annotations

import json
import re
import time
from typing import Any, Type

import tiktoken
from langchain_openai import ChatOpenAI
from openai import APIStatusError, RateLimitError
from pydantic import BaseModel

from app.core.logging_utils import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)


class LLMResponseError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def get_llm(model: str | None = None, temperature: float = 0.0, **kwargs) -> ChatOpenAI:
    """Create and return a configured ChatOpenAI instance.

    Centralizes LLM instantiation so model/temperature defaults live in one place.
    """
    try:
        settings = get_settings()
        resolved_model = model or settings.openrouter_model
        # Keep structured JSON output enabled by default for extraction-style tasks.
        default_model_kwargs = {"response_format": {"type": "json_object"}}
        provided_mk = kwargs.pop("model_kwargs", None)
        if isinstance(provided_mk, dict):
            model_kwargs = {**default_model_kwargs, **provided_mk}
        else:
            model_kwargs = default_model_kwargs
        reasoning = kwargs.pop("reasoning", {"effort": "none"})
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
            reasoning=reasoning,
            model_kwargs=model_kwargs,
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
    include_raw: bool = False,
    **kwargs,
):
    """Return an LLM instance configured for structured output.

    This calls `with_structured_output(output_model)` on the underlying LLM
    and surfaces errors clearly.
    """
    llm = get_llm(model=model, temperature=temperature, **kwargs)
    try:
        structured = llm.with_structured_output(output_model, include_raw=include_raw)
        return structured
    except Exception as exc:
        logger.error("LLM does not support structured output: %s", exc, exc_info=True)
        raise


def estimate_tokens(text: str, model: str | None = None) -> int:
    if not text:
        return 0

    try:
        encoding = (
            tiktoken.encoding_for_model(model)
            if model
            else tiktoken.get_encoding("cl100k_base")
        )
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def extract_llm_metadata(result: Any) -> tuple[Any, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    parsed = result

    if isinstance(result, dict) and "parsed" in result:
        parsed = result.get("parsed")
        raw = result.get("raw")
        parsing_error = result.get("parsing_error")
        if parsing_error is not None:
            metadata["parsing_error"] = str(parsing_error)
        if raw is not None:
            usage = getattr(raw, "usage_metadata", None) or {}
            response_metadata = getattr(raw, "response_metadata", None) or {}
            metadata["usage_input_tokens"] = usage.get("input_tokens")
            metadata["usage_output_tokens"] = usage.get("output_tokens")
            metadata["usage_total_tokens"] = usage.get("total_tokens")
            metadata["finish_reason"] = response_metadata.get("finish_reason")
            metadata["model_name"] = response_metadata.get("model_name")

    return parsed, {key: value for key, value in metadata.items() if value is not None}


def extract_message_metadata(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage_metadata", None) or {}
    response_metadata = getattr(message, "response_metadata", None) or {}
    metadata = {
        "usage_input_tokens": usage.get("input_tokens"),
        "usage_output_tokens": usage.get("output_tokens"),
        "usage_total_tokens": usage.get("total_tokens"),
        "finish_reason": response_metadata.get("finish_reason"),
        "model_name": response_metadata.get("model_name"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def escape_json_control_chars(text: str) -> str:
    escaped: list[str] = []
    in_string = False
    escape = False

    for char in text:
        if escape:
            escaped.append(char)
            escape = False
            continue
        if char == "\\":
            escaped.append(char)
            escape = True
            continue
        if char == '"':
            escaped.append(char)
            in_string = not in_string
            continue

        if in_string:
            if char == "\n":
                escaped.append("\\n")
                continue
            if char == "\r":
                escaped.append("\\r")
                continue
            if char == "\t":
                escaped.append("\\t")
                continue
            if ord(char) < 32:
                escaped.append(f"\\u{ord(char):04x}")
                continue

        escaped.append(char)

    return "".join(escaped)


def sanitize_json_text(text: str) -> str:
    return escape_json_control_chars(strip_code_fences(text))


def parse_model_json(content: str, output_model: Type[BaseModel]) -> BaseModel:
    sanitized = sanitize_json_text(content)
    parsed_json = json.loads(sanitized)
    return output_model.model_validate(parsed_json)


def coerce_message_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
            else:
                text_parts.append(str(item))
        return "\n".join(part for part in text_parts if part).strip()

    return str(content)


async def invoke_structured_llm(chain, payload: dict):
    started = time.perf_counter()
    try:
        result = await chain.ainvoke(payload)
    except RateLimitError as exc:
        elapsed = time.perf_counter() - started
        logger.warning("structured LLM rate limited after %.2fs: %s", elapsed, exc)
        raise LLMProviderError(
            (
                "The configured model provider is rate-limiting requests. "
                "Retry shortly or use a non-free model/key."
            ),
            status_code=503,
        ) from exc
    except APIStatusError as exc:
        elapsed = time.perf_counter() - started
        logger.error("structured LLM provider error after %.2fs: %s", elapsed, exc, exc_info=True)
        raise LLMProviderError(
            f"Upstream model provider returned HTTP {exc.status_code}.",
            status_code=502,
        ) from exc
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.error("structured LLM call failed after %.2fs: %s", elapsed, exc, exc_info=True)
        raise

    elapsed = time.perf_counter() - started
    parsed, metadata = extract_llm_metadata(result)
    metadata_str = (
        " ".join(f"{key}={value}" for key, value in metadata.items()) or "no_usage_metadata"
    )
    logger.info("structured LLM call completed in %.2fs %s", elapsed, metadata_str)
    return parsed, metadata


async def invoke_json_llm(llm, prompt, payload: dict, output_model: Type[BaseModel]):
    started = time.perf_counter()
    try:
        messages = prompt.format_messages(**payload)
        response = await llm.ainvoke(messages)
        content = coerce_message_text_content(response.content)
        parsed = parse_model_json(content, output_model)
    except (json.JSONDecodeError, ValueError) as exc:
        elapsed = time.perf_counter() - started
        logger.error("JSON LLM parse failed after %.2fs: %s", elapsed, exc, exc_info=True)
        raise LLMResponseError("LLM returned invalid JSON") from exc
    except RateLimitError as exc:
        elapsed = time.perf_counter() - started
        logger.warning("JSON LLM rate limited after %.2fs: %s", elapsed, exc)
        raise LLMProviderError(
            (
                "The configured model provider is rate-limiting requests. "
                "Retry shortly or use a non-free model/key."
            ),
            status_code=503,
        ) from exc
    except APIStatusError as exc:
        elapsed = time.perf_counter() - started
        logger.error("JSON LLM provider error after %.2fs: %s", elapsed, exc, exc_info=True)
        raise LLMProviderError(
            f"Upstream model provider returned HTTP {exc.status_code}.",
            status_code=502,
        ) from exc
    except Exception as exc:
        elapsed = time.perf_counter() - started
        logger.error("JSON LLM call failed after %.2fs: %s", elapsed, exc, exc_info=True)
        raise

    elapsed = time.perf_counter() - started
    metadata = extract_message_metadata(response)
    metadata_str = (
        " ".join(f"{key}={value}" for key, value in metadata.items()) or "no_usage_metadata"
    )
    logger.info("JSON LLM call completed in %.2fs %s", elapsed, metadata_str)
    return parsed, metadata
