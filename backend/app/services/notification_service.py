"""
알림 서비스
Slack, Email 등 다양한 채널로 알림 발송
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class NotificationService:
    """알림 서비스 (Slack, Email)"""

    def __init__(self):
        # Slack 설정
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.slack_channel = os.getenv("SLACK_CHANNEL", "#alerts")
        self.slack_enabled = bool(self.slack_webhook_url)

        # Email 설정
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_user)
        self.email_to = os.getenv("ALERT_EMAIL_TO", "").split(",")
        self.email_enabled = bool(self.smtp_user and self.smtp_password)

        if not self.slack_enabled and not self.email_enabled:
            logger.warning(
                "No notification channels configured. "
                "Set SLACK_WEBHOOK_URL or SMTP credentials."
            )

    async def send_slack_notification(
        self,
        message: str,
        title: Optional[str] = None,
        level: str = "warning",
        fields: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Slack 알림 발송

        Args:
            message: 메시지 본문
            title: 제목 (선택)
            level: 알림 레벨 (info, warning, error, critical)
            fields: 추가 필드 (key-value)

        Returns:
            성공 여부
        """
        if not self.slack_enabled:
            logger.debug("Slack notifications disabled")
            return False

        try:
            # 레벨별 색상
            color_map = {
                "info": "#36a64f",  # 녹색
                "warning": "#ff9900",  # 주황색
                "error": "#ff0000",  # 빨간색
                "critical": "#8b0000",  # 진한 빨간색
            }
            color = color_map.get(level, "#808080")

            # 레벨별 이모지
            emoji_map = {
                "info": ":information_source:",
                "warning": ":warning:",
                "error": ":x:",
                "critical": ":rotating_light:",
            }
            emoji = emoji_map.get(level, ":bell:")

            # Slack 메시지 구성
            attachment = {
                "color": color,
                "title": f"{emoji} {title}" if title else f"{emoji} Alert",
                "text": message,
                "footer": "Triflow AI",
                "ts": int(datetime.utcnow().timestamp()),
            }

            # 추가 필드
            if fields:
                attachment["fields"] = [
                    {"title": key, "value": value, "short": True}
                    for key, value in fields.items()
                ]

            payload = {
                "channel": self.slack_channel,
                "attachments": [attachment],
            }

            # Webhook 호출
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.slack_webhook_url,
                    json=payload,
                )

            if response.status_code == 200:
                logger.info(f"Slack notification sent: {title}")
                return True
            else:
                logger.error(
                    f"Slack notification failed: {response.status_code} {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def send_email_notification(
        self,
        subject: str,
        body: str,
        html: Optional[str] = None,
        to: Optional[list[str]] = None,
    ) -> bool:
        """
        Email 알림 발송

        Args:
            subject: 이메일 제목
            body: 이메일 본문 (텍스트)
            html: HTML 본문 (선택)
            to: 수신자 목록 (선택, 기본값은 환경변수)

        Returns:
            성공 여부
        """
        if not self.email_enabled:
            logger.debug("Email notifications disabled")
            return False

        try:
            # 수신자 목록
            recipients = to or self.email_to
            if not recipients:
                logger.error("No email recipients configured")
                return False

            # 이메일 메시지 구성
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = ", ".join(recipients)

            # 텍스트 본문
            text_part = MIMEText(body, "plain")
            msg.attach(text_part)

            # HTML 본문 (선택)
            if html:
                html_part = MIMEText(html, "html")
                msg.attach(html_part)

            # SMTP 전송
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent: {subject} to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_notification(
        self,
        message: str,
        title: Optional[str] = None,
        level: str = "warning",
        fields: Optional[Dict[str, str]] = None,
        email_subject: Optional[str] = None,
        email_body: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        모든 채널로 알림 발송

        Args:
            message: 메시지 (Slack용)
            title: 제목
            level: 레벨
            fields: 추가 필드
            email_subject: 이메일 제목 (선택)
            email_body: 이메일 본문 (선택)

        Returns:
            {"slack": bool, "email": bool}
        """
        results = {}

        # Slack 알림
        if self.slack_enabled:
            results["slack"] = await self.send_slack_notification(
                message=message,
                title=title,
                level=level,
                fields=fields,
            )

        # Email 알림
        if self.email_enabled:
            email_subject_final = email_subject or title or "Alert"
            email_body_final = email_body or message
            results["email"] = await self.send_email_notification(
                subject=email_subject_final,
                body=email_body_final,
            )

        return results


# Singleton 인스턴스
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """
    알림 서비스 싱글톤 인스턴스 반환

    Returns:
        NotificationService 인스턴스
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# ============================================
# 편의 함수 (Canary 알림용)
# ============================================


async def send_canary_rollback_alert(
    deployment_id: str,
    ruleset_name: str,
    reason: str,
    rollback_version: Optional[str] = None,
    tenant_name: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Canary 자동 롤백 알림 발송

    Args:
        deployment_id: 배포 ID
        ruleset_name: 룰셋 이름
        reason: 롤백 사유
        rollback_version: 롤백된 버전
        tenant_name: 테넌트 이름

    Returns:
        발송 결과
    """
    notification = get_notification_service()

    title = "🚨 Canary Auto-Rollback Triggered"
    message = (
        f"Canary deployment has been automatically rolled back.\n\n"
        f"*Ruleset:* {ruleset_name}\n"
        f"*Reason:* {reason}\n"
    )

    fields = {
        "Deployment ID": deployment_id[:8],
        "Reason": reason,
    }

    if rollback_version:
        message += f"*Rolled back to:* v{rollback_version}\n"
        fields["Rollback Version"] = f"v{rollback_version}"

    if tenant_name:
        message += f"*Tenant:* {tenant_name}\n"
        fields["Tenant"] = tenant_name

    message += "\n:point_right: Check deployment logs for details."

    email_subject = f"[Triflow AI] Canary Auto-Rollback: {ruleset_name}"
    email_body = (
        f"Canary Auto-Rollback Alert\n"
        f"========================\n\n"
        f"Ruleset: {ruleset_name}\n"
        f"Reason: {reason}\n"
        f"Deployment ID: {deployment_id}\n"
    )

    if rollback_version:
        email_body += f"Rolled back to: v{rollback_version}\n"

    if tenant_name:
        email_body += f"Tenant: {tenant_name}\n"

    email_body += (
        f"\n"
        f"Please check the deployment logs for more details.\n"
        f"\n"
        f"Triflow AI\n"
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

    return await notification.send_notification(
        message=message,
        title=title,
        level="critical",
        fields=fields,
        email_subject=email_subject,
        email_body=email_body,
    )


async def send_canary_warning_alert(
    deployment_id: str,
    ruleset_name: str,
    warnings: list[str],
    tenant_name: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Canary 경고 알림 발송

    Args:
        deployment_id: 배포 ID
        ruleset_name: 룰셋 이름
        warnings: 경고 메시지 목록
        tenant_name: 테넌트 이름

    Returns:
        발송 결과
    """
    notification = get_notification_service()

    title = "⚠️ Canary Warning"
    message = (
        f"Canary deployment has warnings that require attention.\n\n"
        f"*Ruleset:* {ruleset_name}\n"
        f"*Warnings:*\n"
    )

    for i, warning in enumerate(warnings, 1):
        message += f"{i}. {warning}\n"

    fields = {
        "Deployment ID": deployment_id[:8],
        "Warning Count": str(len(warnings)),
    }

    if tenant_name:
        message += f"\n*Tenant:* {tenant_name}"
        fields["Tenant"] = tenant_name

    email_subject = f"[Triflow AI] Canary Warning: {ruleset_name}"
    email_body = (
        f"Canary Warning Alert\n"
        f"===================\n\n"
        f"Ruleset: {ruleset_name}\n"
        f"Deployment ID: {deployment_id}\n"
        f"\nWarnings:\n"
    )

    for i, warning in enumerate(warnings, 1):
        email_body += f"{i}. {warning}\n"

    if tenant_name:
        email_body += f"\nTenant: {tenant_name}\n"

    email_body += (
        f"\n"
        f"Please monitor the deployment closely.\n"
        f"\n"
        f"Triflow AI\n"
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

    return await notification.send_notification(
        message=message,
        title=title,
        level="warning",
        fields=fields,
        email_subject=email_subject,
        email_body=email_body,
    )
