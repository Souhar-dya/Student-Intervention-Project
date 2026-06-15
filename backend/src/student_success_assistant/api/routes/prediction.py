from fastapi import APIRouter, Depends

from student_success_assistant.application.prediction_service import (
    PredictionService,
    get_prediction_service,
)
from student_success_assistant.schemas.prediction import PredictionRequest, PredictionResponse

router = APIRouter(tags=["prediction"])


@router.post("/predict", response_model=PredictionResponse)
def predict(
    request: PredictionRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionResponse:
    return service.predict(request)

