from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_api_base: str = Field(default="", alias="OPENAI_API_BASE")
    openrouter_model: str = Field(
        default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        alias="OPENROUTER_MODEL",
    )
    openai_timeout_seconds: float = Field(default=90.0, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=0, alias="OPENAI_MAX_RETRIES")
    llm_warn_input_tokens: int = Field(default=8000, alias="LLM_WARN_INPUT_TOKENS")
    segment_chunk_max_tokens: int = Field(
        default=5000,
        alias="SEGMENT_CHUNK_MAX_TOKENS",
    )
    segment_chunk_overlap_tokens: int = Field(
        default=150,
        alias="SEGMENT_CHUNK_OVERLAP_TOKENS",
    )
    segment_chunk_delay_seconds: float = Field(
        default=1.0,
        alias="SEGMENT_CHUNK_DELAY_SECONDS",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
