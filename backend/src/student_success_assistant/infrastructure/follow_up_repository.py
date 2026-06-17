from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from student_success_assistant.infrastructure.database import create_tables, db_connection
from student_success_assistant.schemas.follow_up import (
    FollowUpCaseCreateRequest,
    FollowUpCaseEvent,
    FollowUpCaseResponse,
    FollowUpCaseUpdateRequest,
)
from student_success_assistant.schemas.prediction import RiskCategory
from student_success_assistant.schemas.student import StudentProfile


class FollowUpRepository:
    def initialize(self) -> None:
        create_tables()

    def list_cases(self) -> list[FollowUpCaseResponse]:
        self.initialize()
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        case_id, student_id, student_profile, risk_category, risk_score,
                        model_name, recommendation, recommendation_summary, evidence_case_ids,
                        note, status, escalation_target, last_event, plan_followed,
                        attendance_trend, marks_trend, failures_trend, follow_up_decision,
                        follow_up_rationale, follow_up_next_steps, follow_up_confidence,
                        follow_up_generated_by, follow_up_assessed_at, closed_at, created_at,
                        updated_at
                    FROM follow_up_cases
                    ORDER BY
                        CASE WHEN status = 'Closed' THEN 1 ELSE 0 END,
                        updated_at DESC
                    """
                )
                rows = cursor.fetchall()
                case_ids = [row[0] for row in rows]
                events = self._events_by_case(cursor, case_ids)

        return [self._row_to_case(row, events.get(row[0], [])) for row in rows]

    def get_case(self, case_id: str) -> FollowUpCaseResponse | None:
        self.initialize()
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        case_id, student_id, student_profile, risk_category, risk_score,
                        model_name, recommendation, recommendation_summary, evidence_case_ids,
                        note, status, escalation_target, last_event, plan_followed,
                        attendance_trend, marks_trend, failures_trend, follow_up_decision,
                        follow_up_rationale, follow_up_next_steps, follow_up_confidence,
                        follow_up_generated_by, follow_up_assessed_at, closed_at, created_at,
                        updated_at
                    FROM follow_up_cases
                    WHERE case_id = %s
                    """,
                    (case_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                events = self._events_by_case(cursor, [case_id])

        return self._row_to_case(row, events.get(case_id, []))

    def upsert_case(self, request: FollowUpCaseCreateRequest) -> FollowUpCaseResponse:
        self.initialize()
        student_id = request.student.student_id or f"student-{uuid.uuid4().hex[:10]}"
        case_id = student_id
        summary = request.recommendation_summary or _summarize(request.recommendation)
        status = _default_status(request.prediction.risk_category)
        escalation_target = _default_escalation(request.prediction.risk_category)
        last_event = "Analysis refreshed"
        now = _utc_now()

        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO follow_up_cases (
                        case_id, student_id, student_profile, parent_email, school,
                        risk_category, risk_score, model_name, recommendation,
                        recommendation_summary, evidence_case_ids, status, escalation_target,
                        last_event, updated_at
                    )
                    VALUES (
                        %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (case_id) DO UPDATE SET
                        student_profile = EXCLUDED.student_profile,
                        parent_email = EXCLUDED.parent_email,
                        school = EXCLUDED.school,
                        risk_category = EXCLUDED.risk_category,
                        risk_score = EXCLUDED.risk_score,
                        model_name = EXCLUDED.model_name,
                        recommendation = EXCLUDED.recommendation,
                        recommendation_summary = EXCLUDED.recommendation_summary,
                        evidence_case_ids = EXCLUDED.evidence_case_ids,
                        last_event = EXCLUDED.last_event,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        case_id,
                        student_id,
                        json.dumps(request.student.model_dump()),
                        request.student.parent_email,
                        request.student.school,
                        request.prediction.risk_category.value,
                        request.prediction.risk_score,
                        request.prediction.model_name,
                        request.recommendation,
                        summary,
                        json.dumps(request.evidence_case_ids),
                        status,
                        escalation_target,
                        last_event,
                        now,
                    ),
                )
                self._insert_event(
                    cursor,
                    case_id=case_id,
                    event_type="analysis",
                    title=last_event,
                    note=summary,
                    payload={
                        "risk_category": request.prediction.risk_category.value,
                        "risk_score": request.prediction.risk_score,
                        "evidence_case_ids": request.evidence_case_ids,
                    },
                )
            connection.commit()

        case = self.get_case(case_id)
        if case is None:
            raise RuntimeError("Follow-up case could not be loaded after save.")
        return case

    def update_case(
        self,
        case_id: str,
        request: FollowUpCaseUpdateRequest,
        *,
        record_event: bool = True,
        event_title: str = "Follow-up updated",
    ) -> FollowUpCaseResponse | None:
        self.initialize()
        changes = request.model_dump(exclude_unset=True)
        if not changes:
            return self.get_case(case_id)

        field_sql = []
        params: list[Any] = []
        event_payload: dict[str, Any] = {}
        for field, value in changes.items():
            if value is None:
                continue
            if hasattr(value, "value"):
                value = value.value
            field_sql.append(f"{field} = %s")
            params.append(value)
            event_payload[field] = value

        if not field_sql:
            return self.get_case(case_id)

        if "status" in event_payload:
            if event_payload["status"] == "Closed":
                field_sql.append("closed_at = COALESCE(closed_at, now())")
            elif event_payload["status"] == "Removed":
                pass
            else:
                field_sql.append("closed_at = NULL")
        field_sql.append("updated_at = now()")

        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE follow_up_cases
                    SET {", ".join(field_sql)}
                    WHERE case_id = %s
                    """,
                    (*params, case_id),
                )
                if cursor.rowcount == 0:
                    connection.rollback()
                    return None
                if record_event:
                    self._insert_event(
                        cursor,
                        case_id=case_id,
                        event_type="update",
                        title=event_title,
                        note=str(event_payload.get("note") or event_payload.get("last_event") or ""),
                        payload=event_payload,
                    )
            connection.commit()

        if event_payload.get("status") == "Removed":
            return None
        return self.get_case(case_id)

    def store_assessment(
        self,
        *,
        case_id: str,
        decision: str,
        recommended_status: str,
        escalation_target: str,
        rationale: str,
        next_steps: str,
        confidence: float,
        generated_by: str,
        new_risk_category: str | None = None,
    ) -> FollowUpCaseResponse | None:
        self.initialize()
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE follow_up_cases
                    SET
                        status = %s,
                        escalation_target = %s,
                        last_event = %s,
                        follow_up_decision = %s,
                        follow_up_rationale = %s,
                        follow_up_next_steps = %s,
                        follow_up_confidence = %s,
                        follow_up_generated_by = %s,
                        risk_category = COALESCE(%s, risk_category),
                        follow_up_assessed_at = now(),
                        closed_at = CASE WHEN %s = 'Closed' THEN COALESCE(closed_at, now()) ELSE NULL END,
                        updated_at = now()
                    WHERE case_id = %s
                    """,
                    (
                        recommended_status,
                        escalation_target,
                        decision,
                        decision,
                        rationale,
                        next_steps,
                        confidence,
                        generated_by,
                        new_risk_category,
                        recommended_status,
                        case_id,
                    ),
                )
                if cursor.rowcount == 0:
                    connection.rollback()
                    return None
                self._insert_event(
                    cursor,
                    case_id=case_id,
                    event_type="assessment",
                    title=decision,
                    note=rationale,
                    payload={
                        "recommended_status": recommended_status,
                        "escalation_target": escalation_target,
                        "next_steps": next_steps,
                        "confidence": confidence,
                        "generated_by": generated_by,
                    },
                )
            connection.commit()

        return self.get_case(case_id)

    @staticmethod
    def _insert_event(
        cursor: object,
        *,
        case_id: str,
        event_type: str,
        title: str,
        note: str | None,
        payload: dict[str, Any],
    ) -> None:
        cursor.execute(
            """
            INSERT INTO follow_up_events (event_id, case_id, event_type, title, note, payload)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (f"event-{uuid.uuid4().hex}", case_id, event_type, title, note, json.dumps(payload)),
        )

    @staticmethod
    def _events_by_case(cursor: object, case_ids: list[str]) -> dict[str, list[FollowUpCaseEvent]]:
        if not case_ids:
            return {}
        cursor.execute(
            """
            SELECT event_id, case_id, event_type, title, note, payload, created_at
            FROM follow_up_events
            WHERE case_id = ANY(%s)
            ORDER BY created_at DESC
            """,
            (case_ids,),
        )
        events: dict[str, list[FollowUpCaseEvent]] = {}
        for row in cursor.fetchall():
            events.setdefault(row[1], []).append(
                FollowUpCaseEvent(
                    event_id=row[0],
                    event_type=row[2],
                    title=row[3],
                    note=row[4],
                    payload=row[5] or {},
                    created_at=_format_dt(row[6]),
                )
            )
        return events

    @staticmethod
    def _row_to_case(row: tuple[Any, ...], events: list[FollowUpCaseEvent]) -> FollowUpCaseResponse:
        return FollowUpCaseResponse(
            case_id=row[0],
            student_id=row[1],
            student=StudentProfile(**row[2]),
            risk_category=RiskCategory(row[3]),
            risk_score=row[4],
            model_name=row[5],
            recommendation=row[6],
            recommendation_summary=row[7],
            evidence_case_ids=row[8] or [],
            note=row[9],
            status=row[10],
            escalation_target=row[11],
            last_event=row[12],
            plan_followed=row[13],
            attendance_trend=row[14],
            marks_trend=row[15],
            failures_trend=row[16],
            follow_up_decision=row[17],
            follow_up_rationale=row[18],
            follow_up_next_steps=row[19],
            follow_up_confidence=row[20],
            follow_up_generated_by=row[21],
            follow_up_assessed_at=_format_optional_dt(row[22]),
            closed_at=_format_optional_dt(row[23]),
            created_at=_format_dt(row[24]),
            updated_at=_format_dt(row[25]),
            events=events,
        )


def _default_status(risk_category: RiskCategory) -> str:
    if risk_category is RiskCategory.high:
        return "Escalated"
    if risk_category is RiskCategory.low:
        return "Monitoring"
    return "Open"


def _default_escalation(risk_category: RiskCategory) -> str:
    if risk_category is RiskCategory.high:
        return "Counsellor"
    if risk_category is RiskCategory.low:
        return "Class teacher"
    return "Academic advisor"


def _summarize(text: str) -> str:
    cleaned = text.strip()
    return cleaned if len(cleaned) <= 220 else f"{cleaned[:217].strip()}..."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_optional_dt(value: Any) -> str | None:
    if value is None:
        return None
    return _format_dt(value)


def _format_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def get_follow_up_repository() -> FollowUpRepository:
    return FollowUpRepository()
