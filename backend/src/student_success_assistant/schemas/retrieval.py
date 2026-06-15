from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    school: str | None = Field(default=None, min_length=2, max_length=2)
    min_attendance: int | None = Field(default=None, ge=0, le=100)
    max_attendance: int | None = Field(default=None, ge=0, le=100)
    min_failures: int | None = Field(default=None, ge=0, le=4)
    max_failures: int | None = Field(default=None, ge=0, le=4)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    top_k: int = Field(default=5, ge=1, le=20)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class RetrievedCase(BaseModel):
    case_id: str
    student_id: str
    score: float = Field(..., ge=0, le=1)
    school: str
    failures: int
    absences: int
    final_grade: int
    case_text: str


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[RetrievedCase]
