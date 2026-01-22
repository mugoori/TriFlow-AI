"""
I18N API Router
국제화 테스트 및 메시지 조회 API
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.i18n_service import get_i18n_service, get_message

logger = logging.getLogger(__name__)

router = APIRouter()


class TranslateRequest(BaseModel):
    """번역 요청"""
    key: str
    params: Optional[dict] = None


class TranslateResponse(BaseModel):
    """번역 응답"""
    key: str
    language: str
    message: str
    params: Optional[dict] = None


@router.get("/languages")
async def get_supported_languages():
    """
    지원 언어 목록 조회

    Returns:
        {
            "languages": ["ko", "en"],
            "default": "en"
        }
    """
    service = get_i18n_service()
    return {
        "languages": service.get_supported_languages(),
        "default": service.DEFAULT_LANGUAGE,
    }


@router.post("/translate", response_model=TranslateResponse)
async def translate_message(
    request: Request,
    body: TranslateRequest,
):
    """
    메시지 번역

    Request에서 Accept-Language 헤더를 읽어 자동으로 언어 선택

    Args:
        key: 메시지 키 (예: "judgment.high_defect.message")
        params: 템플릿 변수 (예: {"approver": "John"})

    Returns:
        번역된 메시지

    Example:
        POST /api/v1/i18n/translate
        Headers: Accept-Language: ko-KR
        Body: {"key": "workflow.approval_required.message", "params": {"approver": "홍길동"}}

        Response:
        {
            "key": "workflow.approval_required.message",
            "language": "ko",
            "message": "홍길동님의 승인이 필요합니다.",
            "params": {"approver": "홍길동"}
        }
    """
    # Request State에서 언어 추출 (I18N 미들웨어가 설정)
    lang = getattr(request.state, "language", "ko")

    # 메시지 조회
    params = body.params or {}
    message = get_message(body.key, lang, **params)

    return TranslateResponse(
        key=body.key,
        language=lang,
        message=message,
        params=params,
    )


@router.get("/test")
async def test_i18n(request: Request):
    """
    I18N 테스트 엔드포인트

    다양한 메시지를 여러 언어로 출력하여 테스트

    Returns:
        메시지 샘플 목록
    """
    # Request State에서 언어 추출
    lang = getattr(request.state, "language", "ko")

    test_messages = {
        "judgment_high_defect": get_message("judgment.high_defect.message", lang),
        "judgment_normal": get_message("judgment.normal.message", lang),
        "workflow_approval": get_message("workflow.approval_required.message", lang, approver="John"),
        "error_invalid_input": get_message("error.invalid_input.message", lang, field="temperature"),
        "error_not_found": get_message("error.not_found.message", lang, resource="Ruleset"),
        "notification_drift": get_message("notification.drift_detected.message", lang, connector="ERP-DB"),
        "common_success": get_message("common.success", lang),
        "common_completed": get_message("common.completed", lang),
    }

    return {
        "detected_language": lang,
        "messages": test_messages,
    }


@router.post("/reload")
async def reload_messages():
    """
    메시지 파일 재로드 (개발 환경 전용)

    messages.json 파일을 수정한 후 서버 재시작 없이 반영

    Returns:
        성공 여부
    """
    try:
        service = get_i18n_service()
        service.reload_messages()
        return {
            "success": True,
            "message": "Messages reloaded successfully",
        }
    except Exception as e:
        logger.error(f"Failed to reload messages: {e}")
        return {
            "success": False,
            "message": f"Failed to reload: {str(e)}",
        }


logger.info("I18N router initialized")
