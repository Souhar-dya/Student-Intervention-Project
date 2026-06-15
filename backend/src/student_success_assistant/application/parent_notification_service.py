from __future__ import annotations

import smtplib
from email.message import EmailMessage

from student_success_assistant.core.config import get_settings
from student_success_assistant.schemas.parent_notification import (
    ELIGIBLE_PARENT_EMAIL_RISKS,
    ParentEmailRequest,
    ParentEmailResponse,
)


class ParentNotificationService:
    def send_parent_email(self, request: ParentEmailRequest) -> ParentEmailResponse:
        if request.prediction.risk_category not in ELIGIBLE_PARENT_EMAIL_RISKS:
            return ParentEmailResponse(
                eligible=False,
                sent=False,
                delivery_status="skipped",
                recipient=request.parent_email,
                subject=request.subject,
                message="Parent email is only available for medium-risk or high-risk students.",
            )

        settings = get_settings()
        if not settings.smtp_host:
            return ParentEmailResponse(
                eligible=True,
                sent=True,
                delivery_status="simulated",
                recipient=request.parent_email,
                subject=request.subject,
                message="Email prepared. Configure SMTP settings to send real parent emails.",
            )

        message = EmailMessage()
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = request.parent_email
        message["Subject"] = request.subject
        message.set_content(request.body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

        return ParentEmailResponse(
            eligible=True,
            sent=True,
            delivery_status="sent",
            recipient=request.parent_email,
            subject=request.subject,
            message="Parent email sent.",
        )


def get_parent_notification_service() -> ParentNotificationService:
    return ParentNotificationService()
