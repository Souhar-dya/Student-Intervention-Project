from datetime import UTC, datetime
from uuid import uuid4

from student_success_assistant.infrastructure.student_repository import StudentRepository
from student_success_assistant.schemas.feedback import FeedbackRequest, FeedbackResponse

_IN_MEMORY_FEEDBACK: list[dict[str, str | None]] = []


class FeedbackService:
    def __init__(self, repository: StudentRepository | None = None) -> None:
        self._repository = repository or StudentRepository()

    def store_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        feedback_id = str(uuid4())
        try:
            self._repository.store_feedback(
                feedback_id=feedback_id,
                query=request.query,
                recommendation=request.recommendation,
                rating=request.rating.value,
                advisor_note=request.advisor_note,
            )
        except Exception:
            _IN_MEMORY_FEEDBACK.append(
                {
                    "feedback_id": feedback_id,
                    "query": request.query,
                    "recommendation": request.recommendation,
                    "rating": request.rating.value,
                    "advisor_note": request.advisor_note,
                }
            )

        return FeedbackResponse(
            feedback_id=feedback_id,
            stored=True,
            received_at=datetime.now(UTC),
            message=f"Captured {request.rating.value} feedback for future retrieval-based learning.",
        )


def get_feedback_service() -> FeedbackService:
    return FeedbackService()
