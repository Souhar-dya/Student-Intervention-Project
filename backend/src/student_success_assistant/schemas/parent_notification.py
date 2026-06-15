from pydantic import BaseModel, Field, field_validator

from student_success_assistant.schemas.prediction import PredictionResponse, RiskCategory
from student_success_assistant.schemas.student import StudentProfile


class ParentEmailRequest(BaseModel):
    student: StudentProfile
    prediction: PredictionResponse
    recommendation: str = Field(..., min_length=3)
    parent_email: str = Field(..., min_length=3, max_length=254)
    subject: str = Field(..., min_length=3, max_length=160)
    body: str = Field(..., min_length=10, max_length=5000)

    @field_validator("parent_email")
    @classmethod
    def validate_parent_email(cls, value: str) -> str:
        normalized = value.strip()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid parent email address.")
        return normalized


class ParentEmailResponse(BaseModel):
    eligible: bool
    sent: bool
    delivery_status: str
    recipient: str
    subject: str
    message: str


ELIGIBLE_PARENT_EMAIL_RISKS = {RiskCategory.medium, RiskCategory.high}
