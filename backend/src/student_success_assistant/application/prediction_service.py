import pickle
from pathlib import Path
from typing import Any

from student_success_assistant.core.config import get_settings
from student_success_assistant.domain.model_names import ADVISOR_SCORE_MODEL
from student_success_assistant.schemas.prediction import (
    FeatureContribution,
    PredictionRequest,
    PredictionResponse,
    RiskCategory,
)

BASE_RISK = 0.12
GRADE_RISK_CAP = 0.38
MAX_RISK_SCORE = 0.99
MIN_RISK_SCORE = 0.01


class PredictionService:
    def predict(self, request: PredictionRequest) -> PredictionResponse:
        settings = get_settings()
        model_name = request.model_name or settings.prediction_model
        if model_name == ADVISOR_SCORE_MODEL:
            return self._predict_with_baseline(request, model_name=model_name)

        model_response = self._predict_with_artifact(request, model_name=model_name)
        if model_response is not None:
            return model_response

        return self._predict_with_baseline(request, model_name=settings.prediction_model)

    def _predict_with_artifact(
        self,
        request: PredictionRequest,
        *,
        model_name: str,
    ) -> PredictionResponse | None:
        settings = get_settings()
        artifact_path = Path(settings.model_dir) / f"{model_name}.pkl"
        if not artifact_path.exists():
            artifact_path = Path(settings.model_dir) / f"{settings.selected_model}.pkl"
        if not artifact_path.exists():
            return None

        with artifact_path.open("rb") as handle:
            model = pickle.load(handle)

        student = request.student
        features = self._feature_dict(request)
        probability = float(model.predict_proba([features])[0][1])
        risk_score = round(1 - probability, 3)
        category = self._category(risk_score)

        return PredictionResponse(
            student_id=student.student_id,
            risk_score=risk_score,
            risk_category=category,
            model_name=artifact_path.stem,
            top_contributors=self._artifact_contributors(model, features, request, risk_score),
        )

    def _predict_with_baseline(
        self,
        request: PredictionRequest,
        *,
        model_name: str,
    ) -> PredictionResponse:
        student = request.student
        components = self._baseline_contributors(request)
        raw_score = sum(item.contribution for item in components)
        risk_score = min(max(raw_score, MIN_RISK_SCORE), MAX_RISK_SCORE)

        return PredictionResponse(
            student_id=student.student_id,
            risk_score=round(risk_score, 3),
            risk_category=self._category(risk_score),
            model_name=model_name,
            top_contributors=self._with_score_adjustment(components, risk_score, raw_score),
        )

    @staticmethod
    def _category(risk_score: float) -> RiskCategory:
        if risk_score >= 0.62:
            return RiskCategory.high
        if risk_score >= 0.32:
            return RiskCategory.medium
        return RiskCategory.low

    @staticmethod
    def _baseline_contributors(request: PredictionRequest) -> list[FeatureContribution]:
        student = request.student
        attendance_risk = round(min(max((85 - student.attendance) / 85, 0) * 0.3, 0.3), 3)
        grade_gap = max((10 - student.previous_grade_average) / 10, 0)
        grade_severity = (0.65 * grade_gap) + (0.35 * (grade_gap**2))
        grade_risk = round(min(grade_severity * GRADE_RISK_CAP, GRADE_RISK_CAP), 3)
        return [
            FeatureContribution(feature="base_risk", contribution=BASE_RISK),
            FeatureContribution(feature="failures", contribution=round(min(student.failures * 0.16, 0.48), 3)),
            FeatureContribution(feature="attendance_gap", contribution=attendance_risk),
            FeatureContribution(feature="grade_gap", contribution=grade_risk),
            FeatureContribution(
                feature="study_time",
                contribution=round(-min((student.study_time - 1) * 0.03, 0.09), 3),
            ),
        ]

    @staticmethod
    def _feature_dict(request: PredictionRequest) -> dict[str, object]:
        student = request.student
        return {
            "school": student.school,
            "age": student.age,
            "study_time": student.study_time,
            "failures": student.failures,
            "absences": student.absences,
            "g1": student.previous_grade_average,
            "g2": student.previous_grade_average,
        }

    def _artifact_contributors(
        self,
        model: Any,
        features: dict[str, object],
        request: PredictionRequest,
        risk_score: float,
    ) -> list[FeatureContribution]:
        shap_contributors = self._shap_contributors(model, features)
        if shap_contributors:
            return shap_contributors

        linear_contributors = self._model_weight_contributors(model, features)
        if linear_contributors:
            return linear_contributors

        baseline = self._baseline_contributors(request)
        raw_score = sum(item.contribution for item in baseline)
        return self._with_score_adjustment(baseline, risk_score, raw_score)

    @staticmethod
    def _shap_contributors(model: Any, features: dict[str, object]) -> list[FeatureContribution]:
        try:
            import shap
        except ImportError:
            return []

        try:
            vectorizer = model.named_steps["vectorizer"]
            classifier = model.named_steps["classifier"]
            transformed = vectorizer.transform([features])
            feature_names = vectorizer.get_feature_names_out()
        except (AttributeError, KeyError):
            return []

        try:
            dense_input = transformed.toarray()
            explainer = shap.Explainer(classifier, dense_input, feature_names=feature_names)
            values = explainer(dense_input).values
        except Exception:
            try:
                explainer = shap.TreeExplainer(classifier)
                values = explainer.shap_values(transformed.toarray())
            except Exception:
                return []

        values_for_prediction = PredictionService._select_shap_values(values)
        if values_for_prediction is None:
            return []

        return PredictionService._top_named_contributors(feature_names, values_for_prediction)

    @staticmethod
    def _select_shap_values(values: Any):
        try:
            if isinstance(values, list):
                return values[0][0]
            if len(values.shape) == 3:
                return values[0, :, 0]
            return values[0]
        except (AttributeError, IndexError, TypeError):
            return None

    @staticmethod
    def _model_weight_contributors(model: Any, features: dict[str, object]) -> list[FeatureContribution]:
        try:
            vectorizer = model.named_steps["vectorizer"]
            classifier = model.named_steps["classifier"]
            transformed = vectorizer.transform([features])
            feature_names = vectorizer.get_feature_names_out()
        except (AttributeError, KeyError):
            return []

        if hasattr(classifier, "coef_"):
            values = transformed.multiply(classifier.coef_[0]).toarray()[0]
            return PredictionService._top_named_contributors(feature_names, values)

        if hasattr(classifier, "feature_importances_"):
            values = transformed.multiply(classifier.feature_importances_).toarray()[0]
            return PredictionService._top_named_contributors(feature_names, values)

        return []

    @staticmethod
    def _top_named_contributors(feature_names, values) -> list[FeatureContribution]:
        contributors = [
            FeatureContribution(
                feature=str(name).replace("=", "_"),
                contribution=round(float(value), 3),
            )
            for name, value in zip(feature_names, values, strict=False)
            if abs(float(value)) > 0
        ]
        contributors.sort(key=lambda item: abs(item.contribution), reverse=True)
        return contributors[:5]

    @staticmethod
    def _with_score_adjustment(
        components: list[FeatureContribution],
        risk_score: float,
        raw_score: float,
    ) -> list[FeatureContribution]:
        adjustment = round(risk_score - raw_score, 3)
        if adjustment == 0:
            return components

        feature = "score_floor" if adjustment > 0 else "score_cap"
        return [*components, FeatureContribution(feature=feature, contribution=adjustment)]


def get_prediction_service() -> PredictionService:
    return PredictionService()
