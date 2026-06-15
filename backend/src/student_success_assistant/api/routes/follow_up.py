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
)

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
) -> FollowUpCaseResponse:
    try:
        case = repository.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Follow-up case not found.")
        if not case.note.strip():
            raise HTTPException(status_code=400, detail="Add what happened before assessing.")
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
