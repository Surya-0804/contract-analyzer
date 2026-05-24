from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.core.llm import LLMResponseError
from app.nodes import segment
from app.schemas.segment import ClauseBase, SegmentOutput
from app.state import ContractState


@pytest.fixture
def base_state() -> ContractState:
    return {
        "raw_pdf_text": "",
        "document_metadata": {"page_count": 1, "file_size_bytes": 128},
        "clauses": [],
        "contradictions": [],
        "final_report": "",
    }


@pytest.fixture
def install_segment_llm(monkeypatch) -> Callable[..., tuple[list[str], object]]:
    def _install(
        responses: list[tuple[SegmentOutput | None, dict]] | Exception,
        *,
        chunk_max_tokens: int = 5,
        chunk_overlap_tokens: int = 1,
        chunk_delay_seconds: float = 0.0,
    ) -> tuple[list[str], object]:
        recorded_chunks: list[str] = []
        llm = object()
        settings = SimpleNamespace(
            openrouter_model="missing-model-name",
            llm_warn_input_tokens=10_000,
            segment_chunk_max_tokens=chunk_max_tokens,
            segment_chunk_overlap_tokens=chunk_overlap_tokens,
            segment_chunk_delay_seconds=chunk_delay_seconds,
        )

        monkeypatch.setattr(segment, "get_settings", lambda: settings)
        monkeypatch.setattr(segment, "get_llm", lambda temperature=0: llm)

        async def fake_invoke_json_llm(current_llm, prompt, payload, output_model):
            assert current_llm is llm
            assert output_model is SegmentOutput
            recorded_chunks.append(payload["contract_text"])
            if isinstance(responses, Exception):
                raise responses
            index = len(recorded_chunks) - 1
            return responses[index]

        monkeypatch.setattr(segment, "invoke_json_llm", fake_invoke_json_llm)
        return recorded_chunks, llm

    return _install


def test_chunk_text_returns_empty_list_for_empty_input():
    assert segment.chunk_text("", "missing-model-name") == []


def test_chunk_text_splits_long_input_into_multiple_non_empty_chunks():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"

    chunks = segment.chunk_text(text, "missing-model-name", max_tokens=5, overlap=1)

    assert len(chunks) > 1
    assert all(isinstance(chunk, str) and chunk for chunk in chunks)
    assert chunks[0] != text


def test_deduplicate_clauses_removes_normalized_duplicates_and_reassigns_ids():
    clauses = [
        {"clause_id": 99, "heading": "Notice", "raw_text": "30 days notice"},
        {"clause_id": 42, "heading": "Notice Copy", "raw_text": "  30   days notice  "},
        {"clause_id": 7, "heading": "Liability", "raw_text": "Unlimited liability"},
    ]

    deduplicated = segment.deduplicate_clauses(deepcopy(clauses))

    assert deduplicated == [
        {"clause_id": 1, "heading": "Notice", "raw_text": "30 days notice"},
        {"clause_id": 2, "heading": "Liability", "raw_text": "Unlimited liability"},
    ]


@pytest.mark.asyncio
async def test_segment_node_returns_empty_result_without_invoking_llm(
    base_state: ContractState,
    install_segment_llm: Callable[..., tuple[list[str], object]],
):
    recorded_chunks, _ = install_segment_llm([])
    state = {**base_state, "raw_pdf_text": ""}

    result = await segment.segment_node(state)

    assert recorded_chunks == []
    assert result["clauses"] == []
    assert result["llm_metadata"]["segment"] == {
        "chunk_count": 0,
        "usage_input_tokens": 0,
        "usage_output_tokens": 0,
        "usage_total_tokens": 0,
    }


@pytest.mark.asyncio
async def test_segment_node_aggregates_metadata_and_deduplicates_across_chunks(
    base_state: ContractState,
    install_segment_llm: Callable[..., tuple[list[str], object]],
):
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    chunks = segment.chunk_text(text, "missing-model-name", max_tokens=5, overlap=1)
    responses = [
        (
            SegmentOutput(
                clauses=[
                    ClauseBase(
                        clause_id=index * 2 + 1,
                        heading=f"Clause {index + 1}",
                        raw_text=f"unique clause {index + 1}",
                    )
                ]
            ),
            {
                "usage_input_tokens": 10 + index,
                "usage_output_tokens": 2,
                "usage_total_tokens": 12 + index,
            },
        )
        for index in range(len(chunks))
    ]
    responses[-1] = (
        SegmentOutput(
            clauses=[
                ClauseBase(
                    clause_id=99,
                    heading="Duplicate Clause",
                    raw_text="  unique   clause 1  ",
                ),
                ClauseBase(
                    clause_id=100,
                    heading="Compensation",
                    raw_text="Variable pay is 50% of CTC.",
                ),
            ]
        ),
        {
            "usage_input_tokens": 10 + len(chunks) - 1,
            "usage_output_tokens": 2,
            "usage_total_tokens": 12 + len(chunks) - 1,
        },
    )
    recorded_chunks, _ = install_segment_llm(responses)
    state = {
        **base_state,
        "raw_pdf_text": text,
    }

    result = await segment.segment_node(state)

    expected_usage_input = sum(10 + index for index in range(len(chunks)))
    expected_usage_output = 2 * len(chunks)
    expected_usage_total = sum(12 + index for index in range(len(chunks)))

    assert recorded_chunks == chunks
    assert result["clauses"][0] == {
        "clause_id": 1,
        "heading": "Clause 1",
        "raw_text": "unique clause 1",
    }
    assert result["clauses"][-1] == {
        "clause_id": len(chunks),
        "heading": "Compensation",
        "raw_text": "Variable pay is 50% of CTC.",
    }
    assert len(result["clauses"]) == len(chunks)
    assert result["llm_metadata"]["segment"] == {
        "chunk_count": len(chunks),
        "usage_input_tokens": expected_usage_input,
        "usage_output_tokens": expected_usage_output,
        "usage_total_tokens": expected_usage_total,
    }


@pytest.mark.asyncio
async def test_segment_node_propagates_malformed_llm_output(
    base_state: ContractState,
    install_segment_llm: Callable[..., tuple[list[str], object]],
):
    recorded_chunks, _ = install_segment_llm(LLMResponseError("LLM returned invalid JSON"))
    state = {
        **base_state,
        "raw_pdf_text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
    }

    with pytest.raises(LLMResponseError, match="invalid JSON"):
        await segment.segment_node(state)

    assert len(recorded_chunks) == 1
