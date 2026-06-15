from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FeedbackRating(StrEnum):
    useful = "useful"
    not_useful = "not_useful"


class FeedbackRequest(BaseModel):
    query: str = Field(..., min_length=3)
    recommendation: str = Field(..., min_length=3)
    rating: FeedbackRating
    advisor_note: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    feedback_id: str
    stored: bool
    received_at: datetime
    message: str

