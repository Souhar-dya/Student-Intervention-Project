from dataclasses import dataclass


@dataclass(frozen=True)
class StudentCase:
    student_id: str
    school: str
    age: int
    study_time: int
    failures: int
    absences: int
    previous_grade_average: float
    final_grade: int
    outcome: str


def attendance_from_absences(absences: int) -> int:
    return max(0, min(100, 100 - absences))


def outcome_from_grade(final_grade: int) -> str:
    return "Passed" if final_grade >= 10 else "At Risk"


def build_case_narrative(student_case: StudentCase) -> str:
    return (
        f"Student attends {student_case.school} school. "
        f"Age: {student_case.age}. "
        f"Study time level is {student_case.study_time}. "
        f"Previous failures: {student_case.failures}. "
        f"Absences: {student_case.absences}. "
        f"Previous grade average: {student_case.previous_grade_average:.1f}. "
        f"Final grade: {student_case.final_grade}. "
        f"Outcome: {student_case.outcome}."
    )

