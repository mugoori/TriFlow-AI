"""
I18N 미들웨어
Accept-Language 헤더를 파싱하여 Request State에 저장
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class I18nMiddleware(BaseHTTPMiddleware):
    """
    국제화 미들웨어

    Accept-Language 헤더를 파싱하여 Request State에 저장
    """

    async def dispatch(self, request: Request, call_next):
        # Accept-Language 헤더 추출
        accept_language = request.headers.get("Accept-Language", "ko")

        # 언어 정규화 (ko-KR → ko)
        lang = self._parse_language(accept_language)

        # Request State에 저장 (라우터에서 사용 가능)
        request.state.language = lang

        # 다음 미들웨어/핸들러 호출
        response = await call_next(request)

        return response

    def _parse_language(self, accept_language: str) -> str:
        """
        Accept-Language 헤더 파싱

        Args:
            accept_language: "ko-KR,en-US;q=0.9,en;q=0.8"

        Returns:
            "ko" 또는 "en"
        """
        if not accept_language:
            return "ko"  # 기본값

        # 첫 번째 언어 추출
        first_lang = accept_language.split(",")[0].strip()

        # "ko-KR" → "ko"
        lang_code = first_lang.split("-")[0].lower()

        # 지원 언어 체크
        if lang_code in ["ko", "kr", "한"]:
            return "ko"
        elif lang_code in ["en", "us", "gb"]:
            return "en"

        # 기본값
        return "en"
