from enum import StrEnum

from pydantic import BaseModel, Field

from student_success_assistant.schemas.student import StudentProfile


class RiskCategory(StrEnum):
    low = "Low Risk"
    medium = "Medium Risk"
    high = "High Risk"


class PredictionRequest(BaseModel):
    student: StudentProfile
    model_name: str | None = Field(default=None, min_length=1)


class FeatureContribution(BaseModel):
    feature: str
    contribution: float


class PredictionResponse(BaseModel):
    student_id: str | None
    risk_score: float = Field(..., ge=0, le=1)
    risk_category: RiskCategory
    model_name: str
    top_contributors: list[FeatureContribution]
