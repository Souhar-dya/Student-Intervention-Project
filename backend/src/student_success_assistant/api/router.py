from fastapi import APIRouter, Depends

from student_success_assistant.api.routes import (
    admin,
    auth,
    evaluation,
    explanation,
    feedback,
    follow_up,
    health,
    insights,
    parent_notification,
    prediction,
    recommendation,
    retrieval,
)
from student_success_assistant.core.security import require_authenticated_user

api_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])

api_router.include_router(health.router)
api_router.include_router(auth.router)

protected_router.include_router(admin.router)
protected_router.include_router(prediction.router)
protected_router.include_router(retrieval.router)
protected_router.include_router(recommendation.router)
protected_router.include_router(evaluation.router)
protected_router.include_router(explanation.router)
protected_router.include_router(feedback.router)
protected_router.include_router(follow_up.router)
protected_router.include_router(insights.router)
protected_router.include_router(parent_notification.router)
api_router.include_router(protected_router)
