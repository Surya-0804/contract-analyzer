from __future__ import annotations

from pydantic import BaseModel, Field


class ContradictOutput(BaseModel):
    contradictions: list[str] = Field(
        default_factory=list,
        description="Only confirmed logical or numerical contradictions across clauses",
    )
