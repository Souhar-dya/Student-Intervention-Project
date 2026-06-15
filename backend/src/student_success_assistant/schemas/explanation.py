from pydantic import BaseModel

from student_success_assistant.schemas.prediction import FeatureContribution, PredictionRequest, RiskCategory


class ExplanationRequest(BaseModel):
    prediction: PredictionRequest


class ExplanationResponse(BaseModel):
    student_id: str | None
    risk_score: float
    risk_category: RiskCategory
    top_contributors: list[FeatureContribution]
    explanation: str
