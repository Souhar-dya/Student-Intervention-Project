from fastapi import APIRouter, Depends, HTTPException

from student_success_assistant.application.insights_service import (
    InsightsService,
    get_insights_service,
)
from student_success_assistant.schemas.insights import FactorInsightRequest, FactorInsightResponse

router = APIRouter(tags=["insights"])


@router.post("/insights/factors", response_model=FactorInsightResponse)
def summarize_factors(
    request: FactorInsightRequest,
    service: InsightsService = Depends(get_insights_service),
) -> FactorInsightResponse:
    try:
        return service.summarize_factors(request)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
