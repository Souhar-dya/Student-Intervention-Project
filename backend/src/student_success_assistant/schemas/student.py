from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    student_id: str | None = Field(default=None, min_length=1)
    parent_email: str | None = Field(default=None, max_length=254)
    school: str = Field(..., min_length=2, max_length=2)
    age: int = Field(..., ge=15, le=22)
    attendance: int = Field(..., ge=0, le=100)
    failures: int = Field(..., ge=0, le=4)
    absences: int = Field(..., ge=0, le=100)
    study_time: int = Field(..., ge=1, le=4)
    previous_grade_average: float = Field(..., ge=0, le=20)
