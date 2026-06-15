from fastapi import APIRouter, Depends, status

from student_success_assistant.application.feedback_service import FeedbackService, get_feedback_service
from student_success_assistant.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def store_feedback(
    request: FeedbackRequest,
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    return service.store_feedback(request)

