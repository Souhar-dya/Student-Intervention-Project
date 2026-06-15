from __future__ import annotations

from functools import lru_cache

from student_success_assistant.core.config import get_settings


class Reranker:
    def __init__(self, model_name: str, enable_remote_models: bool) -> None:
        self._model_name = model_name
        self._enable_remote_models = enable_remote_models
        self._model = None

    def rerank(self, query: str, cases: list[dict], limit: int) -> list[dict]:
        model = self._load_model()
        if model is None or not cases:
            return cases[:limit]

        pairs = [(query, str(case.get("case_text", ""))) for case in cases]
        scores = model.predict(pairs)
        scored = [
            (float(score), case)
            for score, case in zip(scores, cases, strict=False)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{**case, "score": round(score, 3)} for score, case in scored[:limit]]

    def _load_model(self):
        if not self._enable_remote_models:
            return None
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            return None

        self._model = CrossEncoder(self._model_name)
        return self._model


@lru_cache
def get_reranker() -> Reranker:
    settings = get_settings()
    return Reranker(
        model_name=settings.reranker_model,
        enable_remote_models=settings.enable_remote_models,
    )
