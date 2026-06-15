from pydantic import BaseModel, Field

from student_success_assistant.infrastructure.embeddings import EmbeddingProvider, get_embedding_provider
from student_success_assistant.infrastructure.qdrant_store import QdrantCaseStore
from student_success_assistant.infrastructure.student_repository import StudentRepository


class EmbeddingPipelineResult(BaseModel):
    embedded: int
    uploaded: int
    collection: str
    warnings: list[str] = Field(default_factory=list)


class EmbeddingPipeline:
    def __init__(
        self,
        repository: StudentRepository | None = None,
        case_store: QdrantCaseStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._repository = repository or StudentRepository()
        self._case_store = case_store or QdrantCaseStore()
        self._embedding_provider = embedding_provider or get_embedding_provider()

    def run(self, limit: int = 1000) -> EmbeddingPipelineResult:
        warnings: list[str] = []
        cases = self._repository.list_cases(limit=limit)
        points = []
        for student_case in cases:
            payload = dict(student_case["payload"])
            payload["case_id"] = student_case["case_id"]
            payload["case_text"] = student_case["case_text"]
            vector = self._embedding_provider.embed(student_case["case_text"])
            points.append(
                {
                    "case_id": student_case["case_id"],
                    "vector": vector,
                    "payload": payload,
                }
            )

        self._case_store.ensure_collection()
        uploaded = self._case_store.upsert_cases(points)

        return EmbeddingPipelineResult(
            embedded=len(points),
            uploaded=uploaded,
            collection=self._case_store.collection_name,
            warnings=warnings,
        )


def get_embedding_pipeline() -> EmbeddingPipeline:
    return EmbeddingPipeline()
