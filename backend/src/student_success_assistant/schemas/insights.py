from pydantic import BaseModel, Field


class FactorInsightRequest(BaseModel):
    prompt: str = Field(
        default="What factors influence student success or failure the most?",
        min_length=3,
    )
    path: str | None = None


class FactorInsight(BaseModel):
    feature: str
    association: str
    strength: float
    passed_average: float
    at_risk_average: float
    explanation: str


class FactorInsightResponse(BaseModel):
    prompt: str
    source_path: str
    row_count: int
    summary: str
    answer: str
    generated_by: str
    factors: list[FactorInsight]
