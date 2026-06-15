from fastapi import APIRouter, Depends

from student_success_assistant.application.evaluation_service import (
    EvaluationService,
    get_evaluation_service,
)
from student_success_assistant.schemas.evaluation import EvaluationRequest, EvaluationResponse

router = APIRouter(tags=["evaluation"])


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate(
    request: EvaluationRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationResponse:
    return service.evaluate(request)

