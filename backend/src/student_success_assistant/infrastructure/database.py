from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from student_success_assistant.core.config import get_settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    school TEXT NOT NULL,
    age INTEGER NOT NULL,
    attendance INTEGER NOT NULL,
    failures INTEGER NOT NULL,
    absences INTEGER NOT NULL,
    study_time INTEGER NOT NULL,
    previous_grade_average DOUBLE PRECISION NOT NULL,
    final_grade INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS student_cases (
    case_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    case_text TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    rating TEXT NOT NULL,
    advisor_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    evaluation_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    scores JSONB NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS follow_up_cases (
    case_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    student_profile JSONB NOT NULL,
    parent_email TEXT,
    school TEXT NOT NULL,
    risk_category TEXT NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    model_name TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    recommendation_summary TEXT NOT NULL,
    evidence_case_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    escalation_target TEXT NOT NULL,
    last_event TEXT NOT NULL,
    plan_followed TEXT NOT NULL DEFAULT 'Unknown',
    attendance_trend TEXT NOT NULL DEFAULT 'No new evidence',
    marks_trend TEXT NOT NULL DEFAULT 'No new evidence',
    failures_trend TEXT NOT NULL DEFAULT 'Unknown',
    follow_up_decision TEXT,
    follow_up_rationale TEXT,
    follow_up_next_steps TEXT,
    follow_up_confidence DOUBLE PRECISION,
    follow_up_generated_by TEXT,
    follow_up_assessed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS follow_up_events (
    event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES follow_up_cases(case_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    note TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_follow_up_cases_status ON follow_up_cases(status);
CREATE INDEX IF NOT EXISTS idx_follow_up_events_case_id ON follow_up_events(case_id);
"""


@contextmanager
def db_connection() -> Iterator[object]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("SSA_DATABASE_URL is not configured.")

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install the database extra with `uv sync --extra database`.") from exc

    try:
        with psycopg.connect(_to_psycopg_url(settings.database_url)) as connection:
            yield connection
    except Exception as exc:
        raise RuntimeError(f"Database connection failed: {exc}") from exc


def _to_psycopg_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def create_tables() -> None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_SQL)
        connection.commit()
