# ===================================================
# TriFlow AI - Notifications Router
# 알림 테스트 및 상태 조회 API
# ===================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from app.services.notifications import notification_manager, NotificationStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Request/Response Models ==========

class SlackTestRequest(BaseModel):
    """Slack 알림 테스트 요청"""
    message: str = Field(..., description="전송할 메시지", min_length=1)
    channel: Optional[str] = Field(None, description="채널 (예: #alerts)")
    mention: Optional[str] = Field(None, description="멘션 (예: @user, channel, here)")


class EmailTestRequest(BaseModel):
    """Email 알림 테스트 요청"""
    to: str = Field(..., description="수신자 이메일 (콤마로 구분하여 여러 명 지정 가능)")
    subject: str = Field(default="TriFlow AI 테스트 이메일", description="제목")
    body: str = Field(..., description="본문 내용", min_length=1)
    html_body: Optional[str] = Field(None, description="HTML 본문 (선택)")


class NotificationResponse(BaseModel):
    """알림 전송 결과 응답"""
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


class NotificationStatusResponse(BaseModel):
    """알림 서비스 상태 응답"""
    slack: Dict[str, Any]
    email: Dict[str, Any]
    sms: Dict[str, Any]


# ========== API Endpoints ==========

@router.get("/status", response_model=NotificationStatusResponse)
async def get_notification_status():
    """
    알림 서비스 상태 조회

    각 알림 채널(Slack, Email, SMS)의 활성화 상태와 설정 정보를 반환합니다.
    """
    return notification_manager.get_status()


@router.post("/test/slack", response_model=NotificationResponse)
async def test_slack_notification(request: SlackTestRequest):
    """
    Slack 알림 테스트

    설정된 Slack Webhook URL로 테스트 메시지를 전송합니다.
    SLACK_WEBHOOK_URL 환경변수가 설정되어 있어야 합니다.
    """
    result = await notification_manager.execute_action(
        "send_slack_notification",
        {
            "message": request.message,
            "channel": request.channel,
            "mention": request.mention,
        }
    )

    if result.status == NotificationStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail={
                "status": result.status.value,
                "message": result.message,
                "details": result.details,
            }
        )

    return NotificationResponse(
        status=result.status.value,
        message=result.message,
        details=result.details,
    )


@router.post("/test/email", response_model=NotificationResponse)
async def test_email_notification(request: EmailTestRequest):
    """
    Email 알림 테스트

    설정된 SMTP 서버를 통해 테스트 이메일을 전송합니다.
    SMTP_HOST, SMTP_USER, SMTP_PASSWORD 환경변수가 설정되어 있어야 합니다.
    """
    result = await notification_manager.execute_action(
        "send_email",
        {
            "to": request.to,
            "subject": request.subject,
            "body": request.body,
            "html_body": request.html_body,
        }
    )

    if result.status == NotificationStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail={
                "status": result.status.value,
                "message": result.message,
                "details": result.details,
            }
        )

    return NotificationResponse(
        status=result.status.value,
        message=result.message,
        details=result.details,
    )


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    action_name: str,
    parameters: Dict[str, Any]
):
    """
    범용 알림 전송

    워크플로우에서 호출되는 범용 알림 전송 API입니다.

    - action_name: send_slack_notification, send_email, send_sms
    - parameters: 액션별 파라미터
    """
    result = await notification_manager.execute_action(action_name, parameters)

    return NotificationResponse(
        status=result.status.value,
        message=result.message,
        details=result.details,
    )
