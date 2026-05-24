from __future__ import annotations

from pydantic import BaseModel, Field


class ReportOutput(BaseModel):
    final_report: str = Field(description="Final markdown report for the analyzed contract")
