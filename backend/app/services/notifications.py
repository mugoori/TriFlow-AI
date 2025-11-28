# ===================================================
# TriFlow AI - Notification Services
# Slack, Email, SMS 알림 서비스 구현
# ===================================================

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class NotificationStatus(str, Enum):
    """알림 전송 상태"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # 설정 미완료로 스킵


@dataclass
class NotificationResult:
    """알림 전송 결과"""
    status: NotificationStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class SlackNotificationService:
    """Slack Webhook 알림 서비스"""

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.default_channel = os.getenv("SLACK_DEFAULT_CHANNEL", "#alerts")
        self.enabled = bool(self.webhook_url)

    async def send(
        self,
        message: str,
        channel: Optional[str] = None,
        mention: Optional[str] = None,
        attachments: Optional[list] = None,
    ) -> NotificationResult:
        """
        Slack 메시지 전송

        Args:
            message: 전송할 메시지
            channel: 채널명 (예: #alerts) - Webhook URL에 따라 무시될 수 있음
            mention: 멘션할 사용자 (예: @user, <!channel>, <!here>)
            attachments: Slack attachments 형식
        """
        if not self.enabled:
            logger.warning("Slack 알림이 비활성화됨 (SLACK_WEBHOOK_URL 미설정)")
            return NotificationResult(
                status=NotificationStatus.SKIPPED,
                message="Slack Webhook URL이 설정되지 않았습니다",
                details={"config_missing": "SLACK_WEBHOOK_URL"}
            )

        # 멘션 처리
        if mention:
            if mention.startswith("@"):
                message = f"<{mention}> {message}"
            elif mention in ["channel", "here"]:
                message = f"<!{mention}> {message}"
            else:
                message = f"{mention} {message}"

        # Slack 페이로드 구성
        payload = {
            "text": message,
        }

        # 채널 지정 (Incoming Webhook은 채널 오버라이드 허용 여부에 따라 다름)
        if channel:
            payload["channel"] = channel

        if attachments:
            payload["attachments"] = attachments

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )

                if response.status_code == 200:
                    logger.info(f"Slack 알림 전송 성공: {message[:50]}...")
                    return NotificationResult(
                        status=NotificationStatus.SUCCESS,
                        message="Slack 알림이 전송되었습니다",
                        details={"channel": channel or self.default_channel}
                    )
                else:
                    logger.error(f"Slack 알림 실패: {response.status_code} - {response.text}")
                    return NotificationResult(
                        status=NotificationStatus.FAILED,
                        message=f"Slack 전송 실패: {response.status_code}",
                        details={"status_code": response.status_code, "response": response.text}
                    )

        except httpx.TimeoutException:
            logger.error("Slack 알림 타임아웃")
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message="Slack 전송 타임아웃",
                details={"error": "timeout"}
            )
        except Exception as e:
            logger.error(f"Slack 알림 오류: {e}")
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message=f"Slack 전송 오류: {str(e)}",
                details={"error": str(e)}
            )


class EmailNotificationService:
    """SMTP 이메일 알림 서비스"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user)
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.enabled = bool(self.smtp_host and self.smtp_user and self.smtp_password)

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
    ) -> NotificationResult:
        """
        이메일 전송

        Args:
            to: 수신자 이메일 (콤마로 구분하여 여러 명 지정 가능)
            subject: 제목
            body: 본문 (plain text)
            html_body: HTML 본문 (선택)
            cc: 참조 (선택)
            bcc: 숨은 참조 (선택)
        """
        if not self.enabled:
            logger.warning("Email 알림이 비활성화됨 (SMTP 설정 미완료)")
            return NotificationResult(
                status=NotificationStatus.SKIPPED,
                message="SMTP 설정이 완료되지 않았습니다",
                details={"config_missing": ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"]}
            )

        try:
            # 이메일 메시지 구성
            if html_body:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "plain", "utf-8"))
                msg.attach(MIMEText(html_body, "html", "utf-8"))
            else:
                msg = MIMEText(body, "plain", "utf-8")

            msg["Subject"] = subject
            msg["From"] = self.smtp_from
            msg["To"] = to

            if cc:
                msg["Cc"] = cc
            if bcc:
                msg["Bcc"] = bcc

            # 수신자 목록 구성
            recipients = [addr.strip() for addr in to.split(",")]
            if cc:
                recipients.extend([addr.strip() for addr in cc.split(",")])
            if bcc:
                recipients.extend([addr.strip() for addr in bcc.split(",")])

            # SMTP 연결 및 전송
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)

            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.smtp_from, recipients, msg.as_string())
            server.quit()

            logger.info(f"Email 전송 성공: {to} - {subject}")
            return NotificationResult(
                status=NotificationStatus.SUCCESS,
                message="이메일이 전송되었습니다",
                details={"to": to, "subject": subject}
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP 인증 실패: {e}")
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message="SMTP 인증 실패",
                details={"error": "authentication_failed"}
            )
        except smtplib.SMTPException as e:
            logger.error(f"SMTP 오류: {e}")
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message=f"SMTP 오류: {str(e)}",
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error(f"Email 전송 오류: {e}")
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message=f"Email 전송 오류: {str(e)}",
                details={"error": str(e)}
            )


class SMSNotificationService:
    """SMS 알림 서비스 (플레이스홀더)"""

    def __init__(self):
        # SMS는 V2에서 구현 예정 (국내 SMS API 연동 필요)
        self.enabled = False

    async def send(
        self,
        phone: str,
        message: str,
    ) -> NotificationResult:
        """SMS 전송 (V2 구현 예정)"""
        logger.warning("SMS 알림은 V2에서 지원 예정입니다")
        return NotificationResult(
            status=NotificationStatus.SKIPPED,
            message="SMS 알림은 V2에서 지원 예정입니다",
            details={"phone": phone, "version_required": "V2"}
        )


class NotificationManager:
    """
    알림 통합 관리자

    워크플로우 액션에서 호출되어 적절한 알림 서비스로 라우팅
    """

    def __init__(self):
        self.slack = SlackNotificationService()
        self.email = EmailNotificationService()
        self.sms = SMSNotificationService()

    async def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any]
    ) -> NotificationResult:
        """
        액션 이름에 따라 적절한 알림 서비스 호출

        Args:
            action_name: 액션 이름 (send_slack_notification, send_email, send_sms)
            parameters: 액션 파라미터

        Returns:
            NotificationResult: 전송 결과
        """
        if action_name == "send_slack_notification":
            return await self.slack.send(
                message=parameters.get("message", ""),
                channel=parameters.get("channel"),
                mention=parameters.get("mention"),
            )

        elif action_name == "send_email":
            return await self.email.send(
                to=parameters.get("to", ""),
                subject=parameters.get("subject", "TriFlow AI 알림"),
                body=parameters.get("body", ""),
                html_body=parameters.get("html_body"),
            )

        elif action_name == "send_sms":
            return await self.sms.send(
                phone=parameters.get("phone", ""),
                message=parameters.get("message", ""),
            )

        else:
            logger.warning(f"알 수 없는 알림 액션: {action_name}")
            return NotificationResult(
                status=NotificationStatus.FAILED,
                message=f"알 수 없는 알림 액션: {action_name}",
                details={"action": action_name}
            )

    def get_status(self) -> Dict[str, Any]:
        """알림 서비스 상태 조회"""
        return {
            "slack": {
                "enabled": self.slack.enabled,
                "webhook_configured": bool(self.slack.webhook_url),
            },
            "email": {
                "enabled": self.email.enabled,
                "smtp_host": self.email.smtp_host or "미설정",
            },
            "sms": {
                "enabled": self.sms.enabled,
                "note": "V2에서 지원 예정",
            },
        }


# 싱글톤 인스턴스
notification_manager = NotificationManager()
