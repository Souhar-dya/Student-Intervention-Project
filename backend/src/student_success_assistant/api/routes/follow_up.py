from fastapi import APIRouter, Depends, HTTPException, Query

from student_success_assistant.application.follow_up_service import (
    FollowUpService,
    get_follow_up_service,
)
from student_success_assistant.infrastructure.follow_up_repository import (
    FollowUpRepository,
    get_follow_up_repository,
)
from student_success_assistant.schemas.follow_up import (
    FollowUpAssessmentRequest,
    FollowUpAssessmentResponse,
    FollowUpCaseCreateRequest,
    FollowUpCaseResponse,
    FollowUpCaseUpdateRequest,
    FollowUpDecision,
)
from student_success_assistant.schemas.prediction import RiskCategory

router = APIRouter(tags=["follow-up"])


@router.get("/follow-up/cases", response_model=list[FollowUpCaseResponse])
def list_follow_up_cases(
    repository: FollowUpRepository = Depends(get_follow_up_repository),
) -> list[FollowUpCaseResponse]:
    try:
        return repository.list_cases()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/follow-up/cases", response_model=FollowUpCaseResponse)
def save_follow_up_case(
    request: FollowUpCaseCreateRequest,
    repository: FollowUpRepository = Depends(get_follow_up_repository),
) -> FollowUpCaseResponse:
    try:
        return repository.upsert_case(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/follow-up/cases/{case_id}", response_model=FollowUpCaseResponse)
def update_follow_up_case(
    case_id: str,
    request: FollowUpCaseUpdateRequest,
    record_event: bool = Query(True),
    repository: FollowUpRepository = Depends(get_follow_up_repository),
) -> FollowUpCaseResponse:
    try:
        case = repository.update_case(case_id, request, record_event=record_event)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if case is None:
        raise HTTPException(status_code=404, detail="Follow-up case not found.")
    return case


@router.post("/follow-up/cases/{case_id}/assess", response_model=FollowUpCaseResponse)
def assess_saved_follow_up_case(
    case_id: str,
    service: FollowUpService = Depends(get_follow_up_service),
    repository: FollowUpRepository = Depends(get_follow_up_repository),
    direct_decision: str | None = Query(None),
) -> FollowUpCaseResponse:
    try:
        case = repository.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Follow-up case not found.")
        if not case.note.strip() and direct_decision is None:
            raise HTTPException(status_code=400, detail="Add what happened before assessing.")

        if direct_decision is not None:
            # Advisor bypass — apply their decision directly, no LLM call
            decision_map = {
                "close": ("Close ticket", "Closed", "", None),
                "monitor": ("Monitor", "Monitoring", "", None),
                "escalate": ("Escalate", "Escalated", "Counsellor", RiskCategory.high),
                "downgrade": ("Downgrade risk", "Monitoring", "", RiskCategory.medium),
            }
            norm = direct_decision.strip().lower()
            if norm not in decision_map:
                raise HTTPException(status_code=400, detail=f"Invalid direct_decision: {direct_decision}")
            d, status, target, risk = decision_map[norm]
            assessment = FollowUpAssessmentResponse(
                decision=FollowUpDecision(d),
                recommended_status=status,
                escalation_target=target,
                rationale=f"Advisor requested: {direct_decision}",
                next_steps="",
                confidence=1.0,
                generated_by="advisor",
                new_risk_category=risk,
            )
        else:
            assessment = service.assess(
                FollowUpAssessmentRequest(
                    student=case.student,
                    current_risk_category=case.risk_category,
                    current_risk_score=case.risk_score,
                    recommendation=case.recommendation or case.recommendation_summary,
                    advisor_note=case.note,
                    weeks_since_plan=2,
                    plan_followed=case.plan_followed,
                    attendance_trend=case.attendance_trend,
                    marks_trend=case.marks_trend,
                    failures_trend=case.failures_trend,
                )
            )
        updated = repository.store_assessment(
            case_id=case_id,
            decision=assessment.decision.value,
            recommended_status=assessment.recommended_status,
            escalation_target=assessment.escalation_target,
            rationale=assessment.rationale,
            next_steps=assessment.next_steps,
            confidence=assessment.confidence,
            generated_by=assessment.generated_by,
            new_risk_category=assessment.new_risk_category.value if assessment.new_risk_category else None,
        )
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Follow-up case not found.")
    return updated


@router.post("/follow-up/assess", response_model=FollowUpAssessmentResponse)
def assess_follow_up(
    request: FollowUpAssessmentRequest,
    service: FollowUpService = Depends(get_follow_up_service),
) -> FollowUpAssessmentResponse:
    return service.assess(request)
