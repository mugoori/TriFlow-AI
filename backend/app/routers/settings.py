# ===================================================
# TriFlow AI - Settings Router
# 시스템 설정 관리 API
# ===================================================

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from app.auth.dependencies import require_admin
from app.models import User
from app.services.settings_service import (
    settings_service,
    SETTING_DEFINITIONS,
    encryption_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Request/Response Models ==========

class SettingUpdateRequest(BaseModel):
    """설정 업데이트 요청"""
    value: str = Field(..., description="설정 값")


class SettingResponse(BaseModel):
    """설정 응답"""
    key: str
    value: Optional[str]
    is_set: bool
    source: str  # database, environment, not_set
    category: str
    label: str
    sensitive: bool
    updated_at: Optional[str]


class SettingsListResponse(BaseModel):
    """설정 목록 응답"""
    settings: List[SettingResponse]
    categories: List[str]


class SettingTestResponse(BaseModel):
    """설정 테스트 응답"""
    slack: Dict[str, Any]
    email: Dict[str, Any]


class BulkSettingUpdate(BaseModel):
    """일괄 설정 업데이트"""
    settings: Dict[str, str] = Field(..., description="설정 키-값 맵")


class EmailTestRequest(BaseModel):
    """이메일 테스트 요청"""
    to: str = Field(..., description="수신자 이메일 주소")


# ========== API Endpoints ==========

@router.get("", response_model=SettingsListResponse)
async def list_settings(
    category: Optional[str] = None,
    current_user: User = Depends(require_admin),
):
    """
    시스템 설정 목록 조회 (관리자 전용)

    - 민감 정보는 마스킹 처리됨
    - category로 필터링 가능: notification, storage, ai
    """
    settings = settings_service.get_all_settings(category)
    categories = list(set(s.get("category", "general") for s in SETTING_DEFINITIONS.values()))

    return SettingsListResponse(
        settings=[SettingResponse(**s) for s in settings],
        categories=sorted(categories),
    )


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    current_user: User = Depends(require_admin),
):
    """
    특정 설정 조회 (관리자 전용)
    """
    if key not in SETTING_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"알 수 없는 설정 키: {key}")

    definition = SETTING_DEFINITIONS[key]
    value = settings_service.get_setting(key)

    # 민감 정보 마스킹
    display_value = None
    if value:
        if definition.get("sensitive"):
            display_value = encryption_service.mask_value(value)
        else:
            display_value = value

    return SettingResponse(
        key=key,
        value=display_value,
        is_set=bool(value),
        source="database" if value else "not_set",
        category=definition.get("category", "general"),
        label=definition.get("label", key),
        sensitive=definition.get("sensitive", False),
        updated_at=None,
    )


@router.put("/{key}")
async def update_setting(
    key: str,
    request: SettingUpdateRequest,
    current_user: User = Depends(require_admin),
):
    """
    설정 업데이트 (관리자 전용)

    - 민감 정보는 자동 암호화
    - 빈 문자열 전송 시 설정 삭제 (환경변수 fallback)
    """
    if key not in SETTING_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"알 수 없는 설정 키: {key}")

    user_email = current_user.email or "unknown"

    # 빈 값이면 삭제 (환경변수 fallback)
    if not request.value.strip():
        success = settings_service.delete_setting(key)
        if success:
            return {"message": f"설정 삭제됨: {key}", "fallback": "environment"}
        raise HTTPException(status_code=500, detail="설정 삭제 실패")

    # 값 저장
    success = settings_service.set_setting(key, request.value, updated_by=user_email)
    if success:
        return {"message": f"설정 저장됨: {key}"}
    raise HTTPException(status_code=500, detail="설정 저장 실패")


@router.delete("/{key}")
async def delete_setting(
    key: str,
    current_user: User = Depends(require_admin),
):
    """
    설정 삭제 (환경변수 fallback으로 복귀)
    """
    if key not in SETTING_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"알 수 없는 설정 키: {key}")

    success = settings_service.delete_setting(key)
    if success:
        return {"message": f"설정 삭제됨: {key}", "fallback": "environment"}
    raise HTTPException(status_code=500, detail="설정 삭제 실패")


@router.post("/bulk")
async def bulk_update_settings(
    request: BulkSettingUpdate,
    current_user: User = Depends(require_admin),
):
    """
    설정 일괄 업데이트 (관리자 전용)
    """
    user_email = current_user.email or "unknown"
    results = {"success": [], "failed": []}

    for key, value in request.settings.items():
        if key not in SETTING_DEFINITIONS:
            results["failed"].append({"key": key, "reason": "unknown_key"})
            continue

        if not value.strip():
            # 빈 값은 삭제
            if settings_service.delete_setting(key):
                results["success"].append({"key": key, "action": "deleted"})
            else:
                results["failed"].append({"key": key, "reason": "delete_failed"})
        else:
            if settings_service.set_setting(key, value, updated_by=user_email):
                results["success"].append({"key": key, "action": "updated"})
            else:
                results["failed"].append({"key": key, "reason": "update_failed"})

    return results


@router.get("/test/notifications", response_model=SettingTestResponse)
async def test_notification_settings(
    current_user: User = Depends(require_admin),
):
    """
    알림 설정 상태 확인 (관리자 전용)

    Slack, Email 설정이 올바르게 되어있는지 확인
    """
    return settings_service.test_notification_settings()


@router.post("/test/slack")
async def test_slack_connection(
    current_user: User = Depends(require_admin),
):
    """
    Slack 연결 테스트 (관리자 전용)

    실제로 테스트 메시지를 전송하여 연결 확인
    """
    from app.services.notifications import notification_manager

    result = await notification_manager.execute_action(
        "send_slack_notification",
        {"message": "TriFlow AI 연결 테스트 메시지입니다."}
    )

    return {
        "status": result.status.value,
        "message": result.message,
        "details": result.details,
    }


@router.post("/test/email")
async def test_email_connection(
    request: EmailTestRequest,
    current_user: User = Depends(require_admin),
):
    """
    Email 연결 테스트 (관리자 전용)

    지정한 이메일로 테스트 메시지 전송
    """
    from app.services.notifications import notification_manager

    result = await notification_manager.execute_action(
        "send_email",
        {
            "to": request.to,
            "subject": "TriFlow AI 이메일 테스트",
            "body": "이 메시지는 TriFlow AI 이메일 설정 테스트입니다.\n\n설정이 올바르게 되어있다면 이 메시지를 받으실 수 있습니다.",
        }
    )

    return {
        "status": result.status.value,
        "message": result.message,
        "details": result.details,
    }
