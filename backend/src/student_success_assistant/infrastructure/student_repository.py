from __future__ import annotations

import json
from typing import Any

from student_success_assistant.infrastructure.database import db_connection


class StudentRepository:
    def initialize(self) -> None:
        from student_success_assistant.infrastructure.database import create_tables

        create_tables()

    def upsert_student_case(
        self,
        *,
        student: dict[str, Any],
        case_id: str,
        case_text: str,
        payload: dict[str, Any],
    ) -> None:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO students (
                        student_id, school, age, attendance, failures, absences, study_time,
                        previous_grade_average, final_grade, outcome, raw_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (student_id) DO UPDATE SET
                        school = EXCLUDED.school,
                        age = EXCLUDED.age,
                        attendance = EXCLUDED.attendance,
                        failures = EXCLUDED.failures,
                        absences = EXCLUDED.absences,
                        study_time = EXCLUDED.study_time,
                        previous_grade_average = EXCLUDED.previous_grade_average,
                        final_grade = EXCLUDED.final_grade,
                        outcome = EXCLUDED.outcome,
                        raw_payload = EXCLUDED.raw_payload
                    """,
                    (
                        student["student_id"],
                        student["school"],
                        student["age"],
                        student["attendance"],
                        student["failures"],
                        student["absences"],
                        student["study_time"],
                        student["previous_grade_average"],
                        student["final_grade"],
                        student["outcome"],
                        json.dumps(student.get("raw_payload", {})),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO student_cases (case_id, student_id, case_text, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (case_id) DO UPDATE SET
                        case_text = EXCLUDED.case_text,
                        payload = EXCLUDED.payload
                    """,
                    (case_id, student["student_id"], case_text, json.dumps(payload)),
                )
            connection.commit()

    def list_cases(self, limit: int = 1000) -> list[dict[str, Any]]:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT case_id, student_id, case_text, payload
                    FROM student_cases
                    ORDER BY case_id
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

        return [
            {
                "case_id": row[0],
                "student_id": row[1],
                "case_text": row[2],
                "payload": row[3],
            }
            for row in rows
        ]

    def search_cases(self, *, filters: dict[str, Any], limit: int = 1000) -> list[dict[str, Any]]:
        where_clauses = []
        params: list[Any] = []
        school = filters.get("school")
        if school:
            where_clauses.append("payload->>'school' = %s")
            params.append(school)
        min_attendance = filters.get("min_attendance")
        if min_attendance is not None:
            where_clauses.append("(payload->>'attendance')::int >= %s")
            params.append(min_attendance)
        max_attendance = filters.get("max_attendance")
        if max_attendance is not None:
            where_clauses.append("(payload->>'attendance')::int <= %s")
            params.append(max_attendance)
        min_failures = filters.get("min_failures")
        if min_failures is not None:
            where_clauses.append("(payload->>'failures')::int >= %s")
            params.append(min_failures)
        max_failures = filters.get("max_failures")
        if max_failures is not None:
            where_clauses.append("(payload->>'failures')::int <= %s")
            params.append(max_failures)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT case_id, student_id, case_text, payload
                    FROM student_cases
                    {where_sql}
                    ORDER BY case_id
                    LIMIT %s
                    """,
                    (*params, limit),
                )
                rows = cursor.fetchall()

        return [
            {
                "case_id": row[0],
                "student_id": row[1],
                "case_text": row[2],
                "payload": row[3],
            }
            for row in rows
        ]

    def store_feedback(
        self,
        *,
        feedback_id: str,
        query: str,
        recommendation: str,
        rating: str,
        advisor_note: str | None,
    ) -> None:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO feedback (feedback_id, query, recommendation, rating, advisor_note)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (feedback_id, query, recommendation, rating, advisor_note),
                )
            connection.commit()

    def store_evaluation(
        self,
        *,
        evaluation_id: str,
        query: str,
        recommendation: str,
        scores: dict[str, float | int],
        notes: str,
    ) -> None:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO evaluation_results (
                        evaluation_id, query, recommendation, scores, notes
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (evaluation_id, query, recommendation, json.dumps(scores), notes),
                )
            connection.commit()

    def list_positive_feedback(self, limit: int) -> list[dict[str, str]]:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT query, recommendation
                    FROM feedback
                    WHERE rating = 'useful'
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

        return [{"query": row[0], "recommendation": row[1]} for row in rows]

    def list_feedback_examples(self, limit: int) -> list[dict[str, str | None]]:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT query, recommendation, rating, advisor_note
                    FROM feedback
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

        return [
            {
                "query": row[0],
                "recommendation": row[1],
                "rating": row[2],
                "advisor_note": row[3],
            }
            for row in rows
        ]

    def list_judged_recommendations(self, limit: int) -> list[dict[str, Any]]:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT query, recommendation, scores, notes
                    FROM evaluation_results
                    ORDER BY (scores->>'overall')::float DESC, created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()

        return [
            {
                "query": row[0],
                "recommendation": row[1],
                "scores": row[2],
                "notes": row[3],
            }
            for row in rows
        ]


def get_student_repository() -> StudentRepository:
    return StudentRepository()
