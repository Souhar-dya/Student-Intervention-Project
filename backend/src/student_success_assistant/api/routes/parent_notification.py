from fastapi import APIRouter, Depends

from student_success_assistant.application.parent_notification_service import (
    ParentNotificationService,
    get_parent_notification_service,
)
from student_success_assistant.schemas.parent_notification import (
    ParentEmailRequest,
    ParentEmailResponse,
)

router = APIRouter(tags=["parent-notification"])


@router.post("/parent-email/send", response_model=ParentEmailResponse)
def send_parent_email(
    request: ParentEmailRequest,
    service: ParentNotificationService = Depends(get_parent_notification_service),
) -> ParentEmailResponse:
    return service.send_parent_email(request)
