from __future__ import annotations

import hashlib
import math
from functools import lru_cache

from student_success_assistant.core.config import get_settings


class EmbeddingProvider:
    def __init__(self, model_name: str, dimension: int, enable_remote_models: bool) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._enable_remote_models = enable_remote_models
        self._model = None

    def embed(self, text: str) -> list[float]:
        model = self._load_model()
        if model is not None:
            return model.encode(text, normalize_embeddings=True).tolist()

        values = [0.0] * self._dimension
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            values[index] += sign

        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def _load_model(self):
        if not self._enable_remote_models:
            return None
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return None

        self._model = SentenceTransformer(self._model_name)
        return self._model


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return EmbeddingProvider(
        model_name=settings.embedding_model,
        dimension=settings.embedding_dimension,
        enable_remote_models=settings.enable_remote_models,
    )
