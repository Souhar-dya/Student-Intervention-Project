from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from student_success_assistant.domain.student_case import (
    StudentCase,
    attendance_from_absences,
    build_case_narrative,
    outcome_from_grade,
)
from student_success_assistant.infrastructure.student_repository import StudentRepository


class IngestionResult(BaseModel):
    source_path: str
    imported: int
    skipped: int
    persisted: bool


class IngestionService:
    def __init__(self, repository: StudentRepository | None = None) -> None:
        self._repository = repository or StudentRepository()

    def ingest_csv(self, path: str, persist: bool = True) -> IngestionResult:
        source_path = Path(path)
        if not source_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {source_path} (resolved: {source_path.resolve()})",
            )

        imported = 0
        skipped = 0
        if persist:
            self._repository.initialize()

        batch: list[tuple[dict[str, Any], str, str, dict[str, Any]]] = []
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            delimiter = ";" if ";" in handle.readline() else ","
            handle.seek(0)
            reader = csv.DictReader(handle, delimiter=delimiter)
            for index, row in enumerate(reader, start=1):
                try:
                    student_case = self._case_from_row(row, index)
                except (KeyError, TypeError, ValueError):
                    skipped += 1
                    continue

                payload = self._payload(student_case, row)
                narrative = build_case_narrative(student_case)
                batch.append((
                    payload,
                    f"case-{student_case.student_id}",
                    narrative,
                    payload | {"case_text": narrative},
                ))
                imported += 1

                if persist and len(batch) >= 500:
                    self._repository.batch_upsert_student_cases(batch)
                    batch.clear()

            if persist and batch:
                self._repository.batch_upsert_student_cases(batch)

        return IngestionResult(
            source_path=str(source_path),
            imported=imported,
            skipped=skipped,
            persisted=persist,
        )

    @staticmethod
    def _case_from_row(row: dict[str, str], index: int) -> StudentCase:
        absences = int(row.get("absences", "0"))
        g1 = int(row.get("G1", "0"))
        g2 = int(row.get("G2", "0"))
        final_grade = int(row.get("G3", "0"))
        school = row.get("school", "NA")

        return StudentCase(
            student_id=row.get("student_id") or f"{school}-{index:04d}",
            school=school,
            age=int(row.get("age", "0")),
            study_time=int(row.get("studytime", row.get("study_time", "1"))),
            failures=int(row.get("failures", "0")),
            absences=absences,
            previous_grade_average=(g1 + g2) / 2,
            final_grade=final_grade,
            outcome=outcome_from_grade(final_grade),
        )

    @staticmethod
    def _payload(student_case: StudentCase, row: dict[str, str]) -> dict[str, Any]:
        return {
            "student_id": student_case.student_id,
            "school": student_case.school,
            "age": student_case.age,
            "attendance": attendance_from_absences(student_case.absences),
            "failures": student_case.failures,
            "absences": student_case.absences,
            "study_time": student_case.study_time,
            "previous_grade_average": student_case.previous_grade_average,
            "final_grade": student_case.final_grade,
            "outcome": student_case.outcome,
            "raw_payload": row,
        }


def get_ingestion_service() -> IngestionService:
    return IngestionService()
