from typing import List, TypedDict, Optional


class Clause(TypedDict, total=False):
    clause_id: int
    heading: str
    raw_text: str

    # Filled in evaluate node
    clause_type: str       # Non_Compete | Notice_Period | IP_Assignment | Lock_In | Compensation | Liability | Other
    risk_score: int   # 1 (safe) → 5 (high risk)
    risk_reasoning: str


class ContractState(TypedDict, total=False):
    # ── Input ─────────────────────────────
    file_bytes: bytes  # from FastAPI upload

    # ── Ingest ────────────────────────────
    raw_pdf_text: str
    document_metadata: dict

    # ── Segment ───────────────────────────
    clauses: List[Clause]

    # ── Contradict ────────────────────────
    contradictions: List[str]

    # ── Report ────────────────────────────
    final_report: str
    llm_metadata: dict
