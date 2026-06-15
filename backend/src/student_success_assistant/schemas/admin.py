from pydantic import BaseModel, Field


class InitializeStorageResponse(BaseModel):
    initialized: bool
    message: str


class IngestDatasetRequest(BaseModel):
    path: str = Field(..., min_length=1)
    persist: bool = True


class IngestDatasetsRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1, max_length=10)
    persist: bool = True


class BuildEmbeddingsRequest(BaseModel):
    limit: int = Field(default=1000, ge=1, le=10000)


class TrainModelsRequest(BaseModel):
    path: str = Field(..., min_length=1)
