from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from student_success_assistant.schemas.prediction import RiskCategory
from student_success_assistant.schemas.prediction import PredictionResponse
from student_success_assistant.schemas.student import StudentProfile


class PlanFollowed(StrEnum):
    fully = "Fully followed"
    partially = "Partially followed"
    not_followed = "Not followed"
    unknown = "Unknown"


class ProgressTrend(StrEnum):
    improved = "Improved"
    no_change = "No clear change"
    worsened = "Worsened"
    no_evidence = "No new evidence"


class FailureTrend(StrEnum):
    decreased = "Decreased"
    no_change = "No change"
    increased = "Increased"
    unknown = "Unknown"


class FollowUpDecision(StrEnum):
    close = "Close ticket"
    monitor = "Monitor"
    escalate = "Escalate"


class FollowUpAssessmentRequest(BaseModel):
    student: StudentProfile
    current_risk_category: RiskCategory
    current_risk_score: float = Field(..., ge=0, le=1)
    recommendation: str = Field(..., min_length=1)
    advisor_note: str = Field(..., min_length=1)
    weeks_since_plan: int = Field(default=2, ge=1, le=12)
    plan_followed: PlanFollowed = PlanFollowed.unknown
    attendance_trend: ProgressTrend = ProgressTrend.no_evidence
    marks_trend: ProgressTrend = ProgressTrend.no_evidence
    failures_trend: FailureTrend = FailureTrend.unknown


class FollowUpAssessmentResponse(BaseModel):
    decision: FollowUpDecision
    recommended_status: str
    escalation_target: str
    rationale: str
    next_steps: str
    confidence: float = Field(..., ge=0, le=1)
    generated_by: str


class FollowUpCaseEvent(BaseModel):
    event_id: str
    event_type: str
    title: str
    note: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class FollowUpCaseCreateRequest(BaseModel):
    student: StudentProfile
    prediction: PredictionResponse
    recommendation: str = ""
    recommendation_summary: str = ""
    evidence_case_ids: list[str] = Field(default_factory=list)


class FollowUpCaseUpdateRequest(BaseModel):
    note: str | None = None
    status: str | None = None
    escalation_target: str | None = None
    last_event: str | None = None
    plan_followed: PlanFollowed | None = None
    attendance_trend: ProgressTrend | None = None
    marks_trend: ProgressTrend | None = None
    failures_trend: FailureTrend | None = None


class FollowUpCaseResponse(BaseModel):
    case_id: str
    student_id: str
    student: StudentProfile
    risk_category: RiskCategory
    risk_score: float = Field(..., ge=0, le=1)
    model_name: str
    recommendation: str
    recommendation_summary: str
    evidence_case_ids: list[str]
    note: str
    status: str
    escalation_target: str
    last_event: str
    plan_followed: PlanFollowed
    attendance_trend: ProgressTrend
    marks_trend: ProgressTrend
    failures_trend: FailureTrend
    follow_up_decision: str | None = None
    follow_up_rationale: str | None = None
    follow_up_next_steps: str | None = None
    follow_up_confidence: float | None = None
    follow_up_generated_by: str | None = None
    follow_up_assessed_at: str | None = None
    closed_at: str | None = None
    created_at: str
    updated_at: str
    events: list[FollowUpCaseEvent] = Field(default_factory=list)
