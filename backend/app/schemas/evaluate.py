from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClauseType = Literal[
    "Non_Compete",
    "Notice_Period",
    "IP_Assignment",
    "Lock_In",
    "Compensation",
    "Liability",
    "Other",
]


class EvaluatedClause(BaseModel):
    clause_id: int = Field(description="Original clause ID")
    clause_type: ClauseType = Field(description="Best-fit clause category")
    risk_score: int = Field(
        ge=1,
        le=5,
        description="Risk score from 1 (safe) to 5 (high risk)",
    )
    risk_reasoning: str = Field(
        description="Short explanation grounded in the clause text and baseline"
    )


class EvaluateOutput(BaseModel):
    clauses: list[EvaluatedClause]
