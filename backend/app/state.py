from typing import Any, List, TypedDict


class Clause(TypedDict, total=False):
    clause_id: int
    heading: str
    raw_text: str

    # Filled in evaluate node
    clause_type: str  # Evaluated category such as Notice_Period or Liability
    risk_score: int  # 1 (safe) -> 5 (high risk)
    risk_reasoning: str


class ContractState(TypedDict, total=False):
    # Input
    file_bytes: bytes

    # Ingestion
    raw_pdf_text: str
    document_metadata: dict

    # Shared controller memory
    goal: str
    plan: List[str]
    step_logs: List[dict[str, Any]]
    retry_counts: dict[str, int]

    # Pipeline outputs
    clauses: List[Clause]
    contradictions: List[str]
    final_report: str
    llm_metadata: dict
