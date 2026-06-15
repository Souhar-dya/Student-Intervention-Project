from pydantic import BaseModel

from student_success_assistant.schemas.prediction import PredictionRequest, RiskCategory
from student_success_assistant.schemas.retrieval import SearchRequest


class RecommendationRequest(BaseModel):
    prediction: PredictionRequest
    search: SearchRequest


class RecommendationResponse(BaseModel):
    student_id: str | None
    risk_category: RiskCategory
    recommendation: str
    reasoning: str
    evidence_case_ids: list[str]

