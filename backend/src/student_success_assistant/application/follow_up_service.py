from __future__ import annotations

import json
import logging

from student_success_assistant.application.llm_client import get_chat_llm

log = logging.getLogger(__name__)
from student_success_assistant.core.config import get_settings
from student_success_assistant.schemas.follow_up import (
    FailureTrend,
    FollowUpAssessmentRequest,
    FollowUpAssessmentResponse,
    FollowUpDecision,
    PlanFollowed,
    ProgressTrend,
)
from student_success_assistant.schemas.prediction import RiskCategory

ESCALATION_BY_RISK = {
    RiskCategory.high: "Counsellor",
    RiskCategory.medium: "Academic advisor",
    RiskCategory.low: "Class teacher",
}


class FollowUpService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def assess(self, request: FollowUpAssessmentRequest) -> FollowUpAssessmentResponse:
        llm_response = self._assess_with_llm(request)
        if llm_response is not None:
            return llm_response
        return self._assess_with_rubric(request)

    def _assess_with_llm(
        self,
        request: FollowUpAssessmentRequest,
    ) -> FollowUpAssessmentResponse | None:
        llm = get_chat_llm(model=self._settings.judge_model, temperature=0)
        if llm is None:
            log.warning("get_chat_llm returned None (judge_model=%s provider=%s)", self._settings.judge_model, self._settings.llm_provider)
            return None

        prompt = (
            "You are an academic case-review assistant. Decide the next ticket action after a "
            "two-week student intervention follow-up. Use only the supplied student risk, advisor "
            "note, and progress signals. Return strict JSON with double-quoted keys: decision, "
            "recommended_status, escalation_target, rationale, next_steps, confidence. "
            "decision must be one of "
            "'Close ticket', 'Monitor', 'Escalate'. recommended_status must be one of 'Closed', "
            "'Monitoring', 'Escalated'. Escalate when progress is weak, the plan was not followed, "
            "failures increased, attendance or marks worsened, or the advisor note says improvement "
            "was tiny. Close only when the plan was followed and attendance or marks clearly improved "
            "without any failure increase. Keep rationale and next_steps concise.\n\n"
            f"Student: {request.student.model_dump()}\n"
            f"Current risk: {request.current_risk_category} at {request.current_risk_score:.2f}\n"
            f"Weeks since plan: {request.weeks_since_plan}\n"
            f"Original recommendation: {request.recommendation}\n"
            f"Advisor note: {request.advisor_note}\n"
            f"Plan followed: {request.plan_followed}\n"
            f"Attendance trend: {request.attendance_trend}\n"
            f"Marks trend: {request.marks_trend}\n"
            f"Failures trend: {request.failures_trend}\n"
        )
        try:
            response = llm.invoke(prompt)
        except Exception as exc:
            log.warning("LLM follow-up assess invoke failed", exc_info=True)
            return None

        try:
            payload = json.loads(str(response.content).strip())
        except json.JSONDecodeError:
            return None

        try:
            return FollowUpAssessmentResponse(
                decision=FollowUpDecision(payload["decision"]),
                recommended_status=str(payload["recommended_status"]),
                escalation_target=str(payload["escalation_target"]),
                rationale=str(payload["rationale"]),
                next_steps=str(payload["next_steps"]),
                confidence=float(payload.get("confidence", 0.75)),
                generated_by="llm",
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _assess_with_rubric(
        self,
        request: FollowUpAssessmentRequest,
    ) -> FollowUpAssessmentResponse:
        positive_signals = 0
        negative_signals = 0

        if request.attendance_trend is ProgressTrend.improved:
            positive_signals += 1
        elif request.attendance_trend is ProgressTrend.worsened:
            negative_signals += 1

        if request.marks_trend is ProgressTrend.improved:
            positive_signals += 1
        elif request.marks_trend is ProgressTrend.worsened:
            negative_signals += 1

        if request.failures_trend is FailureTrend.decreased:
            positive_signals += 1
        elif request.failures_trend is FailureTrend.increased:
            negative_signals += 2

        plan_is_followed = request.plan_followed is PlanFollowed.fully
        plan_is_weak = request.plan_followed in {PlanFollowed.partially, PlanFollowed.not_followed}
        note_is_concerning = _note_has_concern(request.advisor_note)
        note_is_positive = _note_has_progress(request.advisor_note)

        should_escalate = (
            request.current_risk_category is RiskCategory.high and (negative_signals > 0 or not plan_is_followed)
        ) or (
            request.failures_trend is FailureTrend.increased
        ) or (
            plan_is_weak and positive_signals == 0
        ) or (
            negative_signals >= 2
        ) or (
            note_is_concerning and positive_signals < 2
        )

        should_close = (
            not should_escalate
            and plan_is_followed
            and positive_signals >= 2
            and negative_signals == 0
            and request.current_risk_score < 0.65
        )

        if should_escalate:
            return FollowUpAssessmentResponse(
                decision=FollowUpDecision.escalate,
                recommended_status="Escalated",
                escalation_target=_escalation_target_for_request(request),
                rationale=(
                    "The two-week review does not show enough movement to keep the case at the "
                    "same support level."
                ),
                next_steps=(
                    "Escalate the ticket, assign a named owner, and set a short checkpoint for "
                    "attendance, task completion, and the next assessment result."
                ),
                confidence=0.86 if note_is_concerning or negative_signals else 0.78,
                generated_by="deterministic",
            )

        if should_close:
            return FollowUpAssessmentResponse(
                decision=FollowUpDecision.close,
                recommended_status="Closed",
                escalation_target="Class teacher",
                rationale=(
                    "The support plan was followed and the follow-up signals show clear improvement "
                    "without a new failure signal."
                ),
                next_steps=(
                    "Close the ticket and move the student to light monthly monitoring so the gains "
                    "do not fade."
                ),
                confidence=0.82 if note_is_positive else 0.75,
                generated_by="deterministic",
            )

        return FollowUpAssessmentResponse(
            decision=FollowUpDecision.monitor,
            recommended_status="Monitoring",
            escalation_target=ESCALATION_BY_RISK[request.current_risk_category],
            rationale=(
                "The follow-up has mixed or incomplete evidence, so the case should stay open "
                "without immediate escalation."
            ),
            next_steps=(
                "Continue the plan for one more checkpoint and require concrete evidence: attendance "
                "movement, completed work, and the next test or teacher note."
            ),
            confidence=0.68,
            generated_by="deterministic",
        )


def _escalation_target_for_request(request: FollowUpAssessmentRequest) -> str:
    if request.current_risk_category is RiskCategory.high:
        return "Counsellor"
    if request.failures_trend is FailureTrend.increased:
        return "Academic advisor"
    if request.attendance_trend is ProgressTrend.worsened:
        return "Attendance team"
    return "Counsellor" if _note_has_concern(request.advisor_note) else "Academic advisor"


def _note_has_concern(note: str) -> bool:
    lowered = note.lower()
    concern_terms = [
        "barely",
        "declined",
        "failed",
        "missed",
        "not improved",
        "only a tiny bit",
        "stayed low",
        "still low",
        "worse",
    ]
    return any(term in lowered for term in concern_terms)


def _note_has_progress(note: str) -> bool:
    lowered = note.lower()
    progress_terms = ["better", "completed", "followed", "improved", "increased", "recovered"]
    return any(term in lowered for term in progress_terms)


def get_follow_up_service() -> FollowUpService:
    return FollowUpService()
