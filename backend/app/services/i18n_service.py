"""
국제화 (I18N) 서비스
스펙 참조: A-2-3 NFR-I18N-010

다국어 메시지 템플릿 지원
- ko (한국어), en (영어) 우선
- Accept-Language 헤더 인식
- 폴백: 지원하지 않는 언어 → 영어 (기본값)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class I18nService:
    """국제화 서비스"""

    # 지원 언어
    SUPPORTED_LANGUAGES = ["ko", "en"]
    DEFAULT_LANGUAGE = "en"

    def __init__(self):
        self._messages: Dict[str, Dict] = {}
        self._load_messages()

    def _load_messages(self):
        """메시지 파일 로드"""
        messages_file = Path(__file__).parent.parent / "i18n" / "messages.json"

        try:
            with open(messages_file, "r", encoding="utf-8") as f:
                self._messages = json.load(f)
            logger.info(f"I18n messages loaded from {messages_file}")
        except FileNotFoundError:
            logger.warning(f"Messages file not found: {messages_file}, using empty messages")
            self._messages = {}
        except Exception as e:
            logger.error(f"Failed to load messages: {e}")
            self._messages = {}

    def get_message(
        self,
        key: str,
        lang: str = "ko",
        **kwargs
    ) -> str:
        """
        메시지 조회 (템플릿 변수 치환)

        Args:
            key: 메시지 키 (예: "judgment.high_defect.message")
            lang: 언어 코드 (ko, en)
            **kwargs: 템플릿 변수 ({approver} 등)

        Returns:
            번역된 메시지

        Example:
            get_message("workflow.approval_required.message", lang="ko", approver="John")
            → "John님의 승인이 필요합니다."
        """
        # 언어 정규화
        lang = self._normalize_language(lang)

        # 메시지 키 파싱 (점으로 구분된 경로)
        keys = key.split(".")
        message_dict = self._messages

        # 경로 탐색
        for k in keys:
            if isinstance(message_dict, dict) and k in message_dict:
                message_dict = message_dict[k]
            else:
                # 키를 찾을 수 없으면 키 자체 반환
                logger.warning(f"Message key not found: {key}")
                return key

        # 언어별 메시지 추출
        if isinstance(message_dict, dict):
            if lang in message_dict:
                template = message_dict[lang]
            elif self.DEFAULT_LANGUAGE in message_dict:
                template = message_dict[self.DEFAULT_LANGUAGE]
                logger.debug(f"Language {lang} not found for {key}, using {self.DEFAULT_LANGUAGE}")
            else:
                # 첫 번째 언어 사용
                template = next(iter(message_dict.values()), key)
        else:
            template = str(message_dict)

        # 템플릿 변수 치환
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable {e} in {key}")
            return template

    def _normalize_language(self, lang: str) -> str:
        """
        언어 코드 정규화

        Args:
            lang: Accept-Language 헤더 값 (예: "ko-KR,en-US;q=0.9,en;q=0.8")

        Returns:
            정규화된 언어 코드 (ko 또는 en)
        """
        if not lang:
            return self.DEFAULT_LANGUAGE

        # Accept-Language 헤더 파싱
        # "ko-KR,en-US;q=0.9" → ["ko-KR", "en-US"]
        lang = lang.split(",")[0].strip()

        # "ko-KR" → "ko"
        lang = lang.split("-")[0].lower()

        # 지원 언어 체크
        if lang in self.SUPPORTED_LANGUAGES:
            return lang

        # 한글 키워드 체크
        if "ko" in lang or "한" in lang:
            return "ko"

        # 기본값
        return self.DEFAULT_LANGUAGE

    def get_supported_languages(self) -> list[str]:
        """지원 언어 목록 반환"""
        return self.SUPPORTED_LANGUAGES.copy()

    def reload_messages(self):
        """메시지 파일 재로드 (개발 시 유용)"""
        self._load_messages()
        logger.info("I18n messages reloaded")


# 싱글톤 인스턴스
_i18n_service: Optional[I18nService] = None


def get_i18n_service() -> I18nService:
    """I18nService 싱글톤 인스턴스"""
    global _i18n_service
    if _i18n_service is None:
        _i18n_service = I18nService()
    return _i18n_service


def get_message(key: str, lang: str = "ko", **kwargs) -> str:
    """
    편의 함수: 메시지 조회

    Args:
        key: 메시지 키
        lang: 언어 코드
        **kwargs: 템플릿 변수

    Returns:
        번역된 메시지
    """
    service = get_i18n_service()
    return service.get_message(key, lang, **kwargs)
