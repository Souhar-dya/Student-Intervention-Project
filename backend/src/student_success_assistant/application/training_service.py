from __future__ import annotations

import csv
import pickle
from pathlib import Path

from pydantic import BaseModel, Field

from student_success_assistant.core.config import get_settings
from student_success_assistant.domain.model_names import (
    LOGISTIC_REGRESSION_MODEL,
    RANDOM_FOREST_MODEL,
    XGBOOST_MODEL,
)


class ModelMetric(BaseModel):
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None


class TrainingResult(BaseModel):
    source_path: str
    best_model: str
    artifact_path: str
    metrics: list[ModelMetric] = Field(default_factory=list)


class TrainingService:
    def train(self, path: str) -> TrainingResult:
        try:
            from sklearn.compose import ColumnTransformer
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.feature_extraction import DictVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
            from sklearn.model_selection import train_test_split
            from sklearn.pipeline import Pipeline
        except ImportError as exc:
            raise RuntimeError("Install ML dependencies with `uv sync --extra ml`.") from exc

        rows = self._read_rows(path)
        features = [row[0] for row in rows]
        labels = [row[1] for row in rows]
        if len(set(labels)) < 2 or len(labels) < 20:
            raise ValueError("Training requires at least 20 rows with both pass and at-risk outcomes.")

        train_x, test_x, train_y, test_y = train_test_split(
            features,
            labels,
            test_size=0.25,
            random_state=42,
            stratify=labels,
        )
        _ = ColumnTransformer
        candidates = {
            LOGISTIC_REGRESSION_MODEL: LogisticRegression(max_iter=1000, class_weight="balanced"),
            RANDOM_FOREST_MODEL: RandomForestClassifier(
                n_estimators=120,
                max_depth=4,
                random_state=42,
                class_weight="balanced",
            ),
        }
        xgboost = self._xgboost_candidate()
        if xgboost is not None:
            candidates[XGBOOST_MODEL] = xgboost

        metrics: list[ModelMetric] = []
        trained_models = {}
        for name, estimator in candidates.items():
            pipeline = Pipeline([("vectorizer", DictVectorizer()), ("classifier", estimator)])
            pipeline.fit(train_x, train_y)
            predictions = pipeline.predict(test_x)
            probabilities = (
                pipeline.predict_proba(test_x)[:, 1]
                if hasattr(pipeline.named_steps["classifier"], "predict_proba")
                else None
            )
            metric = ModelMetric(
                model_name=name,
                accuracy=round(accuracy_score(test_y, predictions), 4),
                precision=round(precision_score(test_y, predictions, zero_division=0), 4),
                recall=round(recall_score(test_y, predictions, zero_division=0), 4),
                f1=round(f1_score(test_y, predictions, zero_division=0), 4),
                roc_auc=round(roc_auc_score(test_y, probabilities), 4)
                if probabilities is not None
                else None,
            )
            metrics.append(metric)
            trained_models[name] = pipeline

        best = max(metrics, key=lambda metric: metric.f1)
        settings = get_settings()
        artifact_dir = Path(settings.model_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{best.model_name}.pkl"
        with artifact_path.open("wb") as handle:
            pickle.dump(trained_models[best.model_name], handle)

        return TrainingResult(
            source_path=path,
            best_model=best.model_name,
            artifact_path=str(artifact_path),
            metrics=metrics,
        )

    @staticmethod
    def _xgboost_candidate():
        try:
            from xgboost import XGBClassifier
        except ImportError:
            return None

        return XGBClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=42,
        )

    @staticmethod
    def _read_rows(path: str) -> list[tuple[dict[str, object], int]]:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            delimiter = ";" if ";" in handle.readline() else ","
            handle.seek(0)
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows = []
            for row in reader:
                final_grade = int(row["G3"])
                rows.append(
                    (
                        {
                            "school": row["school"],
                            "age": int(row["age"]),
                            "study_time": int(row["studytime"]),
                            "failures": int(row["failures"]),
                            "absences": int(row["absences"]),
                            "g1": int(row["G1"]),
                            "g2": int(row["G2"]),
                        },
                        1 if final_grade >= 10 else 0,
                    )
                )
        return rows


def get_training_service() -> TrainingService:
    return TrainingService()
