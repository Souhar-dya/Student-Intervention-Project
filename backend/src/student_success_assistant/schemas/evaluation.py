from pydantic import BaseModel, Field, computed_field


class EvaluationRequest(BaseModel):
    query: str = Field(..., min_length=3)
    recommendation: str = Field(..., min_length=3)
    evidence_case_ids: list[str] = Field(default_factory=list, max_length=20)


class JudgeScores(BaseModel):
    relevance: int = Field(..., ge=1, le=10)
    groundedness: int = Field(..., ge=1, le=10)
    consistency: int = Field(..., ge=1, le=10)
    usefulness: int = Field(..., ge=1, le=10)

    @computed_field
    @property
    def overall(self) -> float:
        return round(
            (self.relevance + self.groundedness + self.consistency + self.usefulness) / 4,
            2,
        )


class EvaluationResponse(BaseModel):
    scores: JudgeScores
    notes: str

