from fastapi import APIRouter, Depends

from student_success_assistant.application.explanation_service import (
    ExplanationService,
    get_explanation_service,
)
from student_success_assistant.schemas.explanation import ExplanationRequest, ExplanationResponse

router = APIRouter(tags=["explanation"])


@router.post("/explain", response_model=ExplanationResponse)
def explain(
    request: ExplanationRequest,
    service: ExplanationService = Depends(get_explanation_service),
) -> ExplanationResponse:
    return service.explain(request)
