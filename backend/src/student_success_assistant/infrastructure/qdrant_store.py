from __future__ import annotations

import logging

from uuid import NAMESPACE_URL, uuid5

from student_success_assistant.core.config import get_settings

log = logging.getLogger(__name__)


class QdrantCaseStore:
    def __init__(self) -> None:
        self._settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self._settings.qdrant_url and self._settings.qdrant_api_key)

    @property
    def collection_name(self) -> str:
        return self._settings.qdrant_collection

    def ensure_collection(self) -> None:
        client, models = self._client_and_models()
        existing = {collection.name for collection in client.get_collections().collections}
        if self._settings.qdrant_collection in existing:
            if not self.has_sparse_support():
                log.warning("Collection exists without sparse vectors — recreating for hybrid search")
                client.delete_collection(self._settings.qdrant_collection)
            else:
                return

        client.create_collection(
            collection_name=self._settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=self._settings.embedding_dimension,
                distance=models.Distance.COSINE,
            ),
            sparse_vectors_config={
                "text": models.SparseVectorParams(),
            },
        )

    def has_sparse_support(self) -> bool:
        try:
            client, _ = self._client_and_models()
            info = client.get_collection(self._settings.qdrant_collection)
            return bool(info.config.params.sparse_vectors_config)
        except Exception:
            return False

    def upsert_cases(self, points: list[dict]) -> int:
        if not points:
            return 0

        client, models = self._client_and_models()
        client.upsert(
            collection_name=self._settings.qdrant_collection,
            points=[
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, point["case_id"])),
                    vector=point["vector"],
                    payload=point["payload"],
                )
                for point in points
            ],
        )
        return len(points)

    def search(
        self,
        vector: list[float],
        filters: dict | None,
        limit: int,
        query_text: str | None = None,
    ) -> list[dict]:
        client, models = self._client_and_models()
        qdrant_filter = self._build_filter(models, filters or {})

        if query_text and self.has_sparse_support():
            try:
                response = client.search(
                    collection_name=self._settings.qdrant_collection,
                    query_vector=vector,
                    query=query_text,
                    query_filter=qdrant_filter,
                    limit=limit,
                    with_payload=True,
                )
                return [
                    {"id": str(point.id), "score": float(point.score), "payload": point.payload or {}}
                    for point in response
                ]
            except Exception:
                log.warning("Qdrant hybrid search failed, falling back to dense-only", exc_info=True)

        response = client.search(
            collection_name=self._settings.qdrant_collection,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            {"id": str(point.id), "score": float(point.score), "payload": point.payload or {}}
            for point in response
        ]

    def _client_and_models(self):
        if not self.is_configured():
            raise RuntimeError("Qdrant URL and API key must be configured.")

        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:
            raise RuntimeError("Install the retrieval extra with `uv sync --extra retrieval`.") from exc

        client = QdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key,
            timeout=120,
        )
        return client, models

    @staticmethod
    def _build_filter(models, filters: dict):
        conditions = []
        school = filters.get("school")
        if school:
            conditions.append(models.FieldCondition(key="school", match=models.MatchValue(value=school)))
        min_attendance = filters.get("min_attendance")
        if min_attendance is not None:
            conditions.append(
                models.FieldCondition(key="attendance", range=models.Range(gte=min_attendance))
            )
        max_attendance = filters.get("max_attendance")
        if max_attendance is not None:
            conditions.append(
                models.FieldCondition(key="attendance", range=models.Range(lte=max_attendance))
            )
        min_failures = filters.get("min_failures")
        if min_failures is not None:
            conditions.append(models.FieldCondition(key="failures", range=models.Range(gte=min_failures)))
        max_failures = filters.get("max_failures")
        if max_failures is not None:
            conditions.append(models.FieldCondition(key="failures", range=models.Range(lte=max_failures)))

        if not conditions:
            return None
        return models.Filter(must=conditions)


def get_qdrant_case_store() -> QdrantCaseStore:
    return QdrantCaseStore()
