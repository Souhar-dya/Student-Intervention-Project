from student_success_assistant.application.prediction_service import PredictionService
from student_success_assistant.schemas.explanation import ExplanationRequest, ExplanationResponse

SYSTEM_SCORE_COMPONENTS = {"base_risk", "score_cap", "score_floor"}


class ExplanationService:
    def __init__(self, prediction_service: PredictionService | None = None) -> None:
        self._prediction_service = prediction_service or PredictionService()

    def explain(self, request: ExplanationRequest) -> ExplanationResponse:
        prediction = self._prediction_service.predict(request.prediction)
        contributors = sorted(
            [
                item
                for item in prediction.top_contributors
                if item.feature not in SYSTEM_SCORE_COMPONENTS
            ],
            key=lambda contribution: abs(contribution.contribution),
            reverse=True,
        )
        parts = [
            f"{item.feature} moved risk by {item.contribution:+.2f}" for item in contributors[:3]
        ]
        explanation = (
            f"Risk is {prediction.risk_category} at {prediction.risk_score:.0%}. "
            f"Top drivers: {'; '.join(parts)}."
        )

        return ExplanationResponse(
            student_id=prediction.student_id,
            risk_score=prediction.risk_score,
            risk_category=prediction.risk_category,
            top_contributors=prediction.top_contributors,
            explanation=explanation,
        )


def get_explanation_service() -> ExplanationService:
    return ExplanationService()
