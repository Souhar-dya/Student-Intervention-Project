from fastapi import APIRouter, Depends, HTTPException

from student_success_assistant.application.embedding_pipeline import (
    EmbeddingPipeline,
    EmbeddingPipelineResult,
    get_embedding_pipeline,
)
from student_success_assistant.application.ingestion_service import (
    IngestionResult,
    IngestionService,
    get_ingestion_service,
)
from student_success_assistant.application.training_service import (
    TrainingResult,
    TrainingService,
    get_training_service,
)
from student_success_assistant.infrastructure.database import create_tables
from student_success_assistant.schemas.admin import (
    BuildEmbeddingsRequest,
    IngestDatasetRequest,
    IngestDatasetsRequest,
    InitializeStorageResponse,
    TrainModelsRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/storage/init", response_model=InitializeStorageResponse)
def initialize_storage() -> InitializeStorageResponse:
    try:
        create_tables()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return InitializeStorageResponse(initialized=True, message="PostgreSQL tables are ready.")


@router.post("/ingest", response_model=IngestionResult)
def ingest_dataset(
    request: IngestDatasetRequest,
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResult:
    try:
        return service.ingest_csv(path=request.path, persist=request.persist)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ingest/batch", response_model=list[IngestionResult])
def ingest_datasets(
    request: IngestDatasetsRequest,
    service: IngestionService = Depends(get_ingestion_service),
) -> list[IngestionResult]:
    results: list[IngestionResult] = []
    try:
        for path in request.paths:
            results.append(service.ingest_csv(path=path, persist=request.persist))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return results


@router.post("/embeddings/build", response_model=EmbeddingPipelineResult)
def build_embeddings(
    request: BuildEmbeddingsRequest,
    pipeline: EmbeddingPipeline = Depends(get_embedding_pipeline),
) -> EmbeddingPipelineResult:
    try:
        return pipeline.run(limit=request.limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/models/train", response_model=TrainingResult)
def train_models(
    request: TrainModelsRequest,
    service: TrainingService = Depends(get_training_service),
) -> TrainingResult:
    try:
        return service.train(path=request.path)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
