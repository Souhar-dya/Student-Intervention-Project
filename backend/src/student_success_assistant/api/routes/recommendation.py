from fastapi import APIRouter, Depends

from student_success_assistant.application.recommendation_service import (
    RecommendationService,
    get_recommendation_service,
)
from student_success_assistant.schemas.recommendation import RecommendationRequest, RecommendationResponse

router = APIRouter(tags=["recommendation"])


@router.post("/recommend", response_model=RecommendationResponse)
def recommend(
    request: RecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    return service.recommend(request)

