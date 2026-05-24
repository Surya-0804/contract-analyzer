from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ClauseBase(BaseModel):
    clause_id: int = Field(description="Sequential clause number starting from 1")
    heading: str = Field(description="Short heading for this clause, inferred if not explicit")
    raw_text: str = Field(description="Complete original text of the clause, unchanged")


class SegmentOutput(BaseModel):
    clauses: List[ClauseBase]
