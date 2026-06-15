from fastapi import APIRouter, Depends

from student_success_assistant.application.retrieval_service import RetrievalService, get_retrieval_service
from student_success_assistant.schemas.retrieval import SearchRequest, SearchResponse

router = APIRouter(tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    return service.search(request)

