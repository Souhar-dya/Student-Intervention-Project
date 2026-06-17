from __future__ import annotations

import json
import logging
import re

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
        llm_response = self._assess_with_tools(request)
        if llm_response is None:
            llm_response = self._assess_with_llm(request)
        if llm_response is None:
            return self._assess_with_rubric(request)

        # Downgrade only applies to High → Medium. If the student is not High,
        # Downgrade is invalid — map to Close (if trending up) or Monitor (if mixed).
        if llm_response.decision is FollowUpDecision.downgrade and request.current_risk_category is not RiskCategory.high:
            trend_up = (
                request.attendance_trend is ProgressTrend.improved
                and request.marks_trend is ProgressTrend.improved
                and request.failures_trend is not ProgressTrend.worsened
            )
            if trend_up:
                return FollowUpAssessmentResponse(
                    decision=FollowUpDecision.close,
                    recommended_status="Closed",
                    escalation_target="",
                    rationale="Student improved; Low/Medium risk ticket closed.",
                    next_steps="",
                    confidence=llm_response.confidence,
                    generated_by="llm",
                    new_risk_category=None,
                )
            return FollowUpAssessmentResponse(
                decision=FollowUpDecision.monitor,
                recommended_status="Monitoring",
                escalation_target="",
                rationale="Mix of signals; kept at current level.",
                next_steps="",
                confidence=llm_response.confidence,
                generated_by="llm",
                new_risk_category=None,
            )
        return llm_response

    def _assess_with_tools(
        self,
        request: FollowUpAssessmentRequest,
    ) -> FollowUpAssessmentResponse | None:
        llm = get_chat_llm(model=self._settings.judge_model, temperature=0)
        if llm is None:
            return None

        try:
            from langchain_core.tools import tool
        except ImportError:
            return None

        @tool
        def close_ticket(rationale: str, next_steps: str, confidence: float) -> str:
            """Close the follow-up ticket. Use when the student clearly improved, plan was
            followed, and the current risk is Medium — full closure is warranted."""
            return json.dumps(FollowUpAssessmentResponse(
                decision=FollowUpDecision.close,
                recommended_status="Closed",
                escalation_target="",
                rationale=rationale,
                next_steps=next_steps,
                confidence=min(1.0, max(0.0, confidence)),
                generated_by="llm",
            ).model_dump())

        @tool
        def downgrade_ticket(rationale: str, next_steps: str, confidence: float) -> str:
            """Downgrade risk from High to Medium. Use when the student clearly improved
            but the current risk is High, and full closure is premature."""
            return json.dumps(FollowUpAssessmentResponse(
                decision=FollowUpDecision.downgrade,
                recommended_status="Monitoring",
                escalation_target=ESCALATION_BY_RISK[RiskCategory.medium],
                rationale=rationale,
                next_steps=next_steps,
                confidence=min(1.0, max(0.0, confidence)),
                generated_by="llm",
                new_risk_category=RiskCategory.medium,
            ).model_dump())

        @tool
        def escalate_ticket(rationale: str, next_steps: str, confidence: float) -> str:
            """Escalate the risk level to High. Use when progress is weak, the plan was not
            followed, failures increased, or the advisor note flags serious concern."""
            return json.dumps(FollowUpAssessmentResponse(
                decision=FollowUpDecision.escalate,
                recommended_status="Escalated",
                escalation_target=ESCALATION_BY_RISK[RiskCategory.high],
                rationale=rationale,
                next_steps=next_steps,
                confidence=min(1.0, max(0.0, confidence)),
                generated_by="llm",
                new_risk_category=RiskCategory.high,
            ).model_dump())

        @tool
        def monitor_ticket(rationale: str, next_steps: str, confidence: float) -> str:
            """Keep the ticket at the current risk level. Use when signals are mixed,
            incomplete, or unclear — no escalation or closure is appropriate."""
            return json.dumps(FollowUpAssessmentResponse(
                decision=FollowUpDecision.monitor,
                recommended_status="Monitoring",
                escalation_target=ESCALATION_BY_RISK[request.current_risk_category],
                rationale=rationale,
                next_steps=next_steps,
                confidence=min(1.0, max(0.0, confidence)),
                generated_by="llm",
            ).model_dump())

        tools = [close_ticket, downgrade_ticket, escalate_ticket, monitor_ticket]
        llm_with_tools = llm.bind_tools(tools)

        prompt = (
            "You are an academic case-review assistant. Decide the next ticket action after a "
            "two-week student intervention follow-up.\n\n"
            "## Student context\n"
            "Tickets only exist for Medium Risk or High Risk students. "
            "A student at Medium can: Close (if clearly on track) or stay (Monitor/Escalate). "
            "A student at High can: Downgrade to Medium or stay (Monitor/Escalate). "
            "There is no 'Low Risk' ticket — Close removes the ticket entirely.\n\n"
            "## Your task\n"
            "Analyze the student data below, reason step by step, then call ONE of the available "
            "tools with your decision. The tool description tells you when to use it.\n"
            "The advisor note is ground truth — follow it.\n\n"
            "Confidence should be: 0.7-0.8 mixed evidence, 0.8-0.9 clear trend, above 0.9 unambiguous.\n"
            "Keep rationale and next_steps concise (1-2 sentences each).\n\n"
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
            response = llm_with_tools.invoke(prompt)
        except Exception:
            log.warning("LLM tool-calling assess invoke failed", exc_info=True)
            return None

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            return None

        tool_call = tool_calls[0]
        tool_name = tool_call.get("name") if isinstance(tool_call, dict) else tool_call.name
        raw_args = tool_call.get("args") if isinstance(tool_call, dict) else tool_call.args
        if not tool_name or not raw_args:
            return None

        tool_map = {
            "close_ticket": close_ticket,
            "downgrade_ticket": downgrade_ticket,
            "escalate_ticket": escalate_ticket,
            "monitor_ticket": monitor_ticket,
        }
        executor = tool_map.get(tool_name)
        if executor is None:
            return None

        try:
            raw = executor(**raw_args)
            return FollowUpAssessmentResponse(**json.loads(raw))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

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
            "two-week student intervention follow-up. Reason step by step, then return strict "
            "JSON with double-quoted keys: decision, recommended_status, escalation_target, "
            "rationale, next_steps, confidence, new_risk_category.\n\n"
            "## Student context\n"
            "Tickets only exist for Medium Risk or High Risk students. "
            "A student currently at Medium can only: stay at Medium (Monitor/Close) or go up "
            "to High (Escalate). "
            "A student currently at High can only: stay at High (Escalate/Monitor) or go down "
            "to Medium (Downgrade). "
            "There is no 'Low Risk' ticket — Close removes the ticket entirely.\n\n"
            "## Step-by-step reasoning\n"
            "1. Read the advisor note and the student's current risk level.\n"
            "2. Count positive signals: attendance/marks improved, failures did not worsen, "
            "plan was followed, advisor note says positive.\n"
            "3. Count negative signals: attendance/marks worsened, failures increased, plan "
            "not followed, advisor note flags concern.\n"
            "4. Decide direction:\n"
            "   - ESCALATE if negative signals dominate (move risk up one level).\n"
            "   - DOWNGRADE if positive signals dominate AND current risk is High (move "
            "High→Medium; only valid when current is High).\n"
            "   - CLOSE if positive signals dominate AND current risk is Medium (student "
            "clearly on track, no further ticket needed).\n"
            "   - MONITOR if signals are mixed or unclear (keep current risk level).\n\n"
            "## Decision rules\n"
            "decision must be one of: 'Close ticket', 'Monitor', 'Escalate', 'Downgrade risk'.\n"
            "recommended_status must be one of: 'Closed', 'Monitoring', 'Escalated'.\n"
            "new_risk_category: 'High Risk' (for Escalate), 'Medium Risk' (for Downgrade), "
            "or null (for Close/Monitor).\n"
            "The advisor note is ground truth — if the advisor says the student improved, "
            "treat it as true. If the advisor says struggling, trust that.\n"
            "Confidence: 0.7-0.8 mixed evidence, 0.8-0.9 clear trend, above 0.9 unambiguous.\n"
            "Keep rationale and next_steps concise (1-2 sentences each).\n\n"
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
            raw = str(response.content).strip()
            payload = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if match is None:
                return None
            candidate = match.group(0)
            candidate = re.sub(r"(?<![:\w])(\b[a-zA-Z_]\w*)(?=\s*:)", r'"\1"', candidate)
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                return None

        try:
            new_risk = payload.get("new_risk_category")
            if new_risk is not None:
                new_risk = RiskCategory(new_risk)
            return FollowUpAssessmentResponse(
                decision=FollowUpDecision(payload["decision"]),
                recommended_status=str(payload["recommended_status"]),
                escalation_target=str(payload["escalation_target"]),
                rationale=str(payload["rationale"]),
                next_steps=str(payload["next_steps"]),
                confidence=float(payload.get("confidence", 0.75)),
                generated_by="llm",
                new_risk_category=new_risk,
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _rubric_confidence(positive: int, negative: int, plan_followed: bool) -> float:
        total = positive + negative
        if total == 0:
            return 0.5
        ratio = positive / total
        boost = 0.05 if plan_followed else 0.0
        return min(0.95, ratio * 0.7 + 0.3 + boost)

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

        should_downgrade = (
            not should_escalate
            and plan_is_followed
            and positive_signals >= 2
            and negative_signals == 0
            and request.current_risk_category is not RiskCategory.low
        )

        should_close = (
            not should_escalate
            and not should_downgrade
            and plan_is_followed
            and positive_signals >= 2
            and negative_signals == 0
            and request.current_risk_score < 0.65
        )

        if should_escalate:
            new_cat = RiskCategory.high
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
                confidence=self._rubric_confidence(positive_signals, negative_signals, plan_is_followed),
                generated_by="deterministic",
                new_risk_category=new_cat,
            )

        if should_downgrade:
            new_cat = RiskCategory.medium
            return FollowUpAssessmentResponse(
                decision=FollowUpDecision.downgrade,
                recommended_status="Monitoring",
                escalation_target=ESCALATION_BY_RISK[new_cat],
                rationale=(
                    "The student has responded well to the intervention — plan was followed "
                    "with clear improvement. Downgrading the risk level accordingly."
                ),
                next_steps=(
                    "Adjust support level to match the new risk category and continue monitoring."
                ),
                confidence=self._rubric_confidence(positive_signals, negative_signals, plan_is_followed),
                generated_by="deterministic",
                new_risk_category=new_cat,
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
                confidence=self._rubric_confidence(positive_signals, negative_signals, plan_is_followed),
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
            confidence=self._rubric_confidence(positive_signals, negative_signals, plan_is_followed),
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
