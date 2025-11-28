"""
PII (개인식별정보) 패턴 정의 및 마스킹 유틸리티
한국 환경에 맞춘 정규식 패턴
"""
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class PIIPattern:
    """PII 패턴 정의"""
    name: str
    pattern: re.Pattern
    mask_func: callable
    description: str


class PIIPatterns:
    """
    PII 패턴 컬렉션
    한국 개인정보 패턴에 최적화
    """

    # 주민등록번호: 000000-0000000 형식
    # 앞 6자리(생년월일) + 뒤 7자리(성별+출생지역+순번+검증번호)
    RESIDENT_ID = re.compile(
        r'\b(\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01]))'  # 생년월일
        r'[-\s]?'  # 구분자 (하이픈 또는 공백, 선택)
        r'([1-4]\d{6})\b'  # 성별코드 + 나머지 6자리
    )

    # 외국인등록번호: 000000-0000000 (5,6,7,8로 시작)
    FOREIGN_ID = re.compile(
        r'\b(\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01]))'
        r'[-\s]?'
        r'([5-8]\d{6})\b'
    )

    # 여권번호: M12345678 또는 S12345678 형식 (알파벳 1자리 + 숫자 8자리)
    PASSPORT = re.compile(
        r'\b([A-Z])(\d{8})\b',
        re.IGNORECASE
    )

    # 운전면허번호: 00-00-000000-00 형식
    DRIVER_LICENSE = re.compile(
        r'\b(\d{2})[-\s]?(\d{2})[-\s]?(\d{6})[-\s]?(\d{2})\b'
    )

    # 휴대전화번호: 010-0000-0000 또는 01000000000
    PHONE_MOBILE = re.compile(
        r'\b(01[016789])'  # 010, 011, 016, 017, 018, 019
        r'[-.\s]?'
        r'(\d{3,4})'
        r'[-.\s]?'
        r'(\d{4})\b'
    )

    # 일반전화번호: 02-000-0000 또는 031-000-0000
    PHONE_LANDLINE = re.compile(
        r'\b(0\d{1,2})'  # 지역번호 (02, 031, 032 등)
        r'[-.\s]?'
        r'(\d{3,4})'
        r'[-.\s]?'
        r'(\d{4})\b'
    )

    # 이메일 주소
    EMAIL = re.compile(
        r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
    )

    # 신용카드번호: 0000-0000-0000-0000 (16자리)
    CREDIT_CARD = re.compile(
        r'\b(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})\b'
    )

    # 계좌번호: 다양한 형식 (10-14자리 숫자)
    BANK_ACCOUNT = re.compile(
        r'\b(\d{3,4})[-\s]?(\d{2,4})[-\s]?(\d{4,6})\b'
    )

    # IP 주소 (IPv4)
    IP_ADDRESS = re.compile(
        r'\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b'
    )

    @classmethod
    def get_all_patterns(cls) -> List[Tuple[str, re.Pattern, str]]:
        """
        모든 PII 패턴 반환
        Returns: [(패턴명, 컴파일된 정규식, 설명), ...]
        """
        return [
            ("resident_id", cls.RESIDENT_ID, "주민등록번호"),
            ("foreign_id", cls.FOREIGN_ID, "외국인등록번호"),
            ("passport", cls.PASSPORT, "여권번호"),
            ("driver_license", cls.DRIVER_LICENSE, "운전면허번호"),
            ("phone_mobile", cls.PHONE_MOBILE, "휴대전화번호"),
            ("phone_landline", cls.PHONE_LANDLINE, "일반전화번호"),
            ("email", cls.EMAIL, "이메일"),
            ("credit_card", cls.CREDIT_CARD, "신용카드번호"),
            ("bank_account", cls.BANK_ACCOUNT, "계좌번호"),
            ("ip_address", cls.IP_ADDRESS, "IP주소"),
        ]


def _mask_resident_id(match: re.Match) -> str:
    """주민등록번호 마스킹: 901231-******* """
    birth = match.group(1)
    return f"{birth}-*******"


def _mask_phone(match: re.Match) -> str:
    """전화번호 마스킹: 010-****-5678"""
    prefix = match.group(1)
    suffix = match.group(3)
    return f"{prefix}-****-{suffix}"


def _mask_email(match: re.Match) -> str:
    """이메일 마스킹: u***@e***.com"""
    local = match.group(1)
    domain = match.group(2)
    domain_parts = domain.split('.')
    masked_local = local[0] + "***" if len(local) > 0 else "***"
    masked_domain = domain_parts[0][0] + "***" if len(domain_parts[0]) > 0 else "***"
    return f"{masked_local}@{masked_domain}.{'.'.join(domain_parts[1:])}"


def _mask_credit_card(match: re.Match) -> str:
    """신용카드 마스킹: 1234-****-****-5678"""
    first = match.group(1)
    last = match.group(4)
    return f"{first}-****-****-{last}"


def _mask_bank_account(match: re.Match) -> str:
    """계좌번호 마스킹: 123-**-****56"""
    first = match.group(1)
    last = match.group(3)[-2:] if len(match.group(3)) >= 2 else "**"
    return f"{first}-**-****{last}"


def _mask_passport(match: re.Match) -> str:
    """여권번호 마스킹: M****5678"""
    letter = match.group(1)
    numbers = match.group(2)
    return f"{letter}****{numbers[-4:]}"


def _mask_driver_license(match: re.Match) -> str:
    """운전면허번호 마스킹: 11-**-******-**"""
    first = match.group(1)
    return f"{first}-**-******-**"


def _mask_ip_address(match: re.Match) -> str:
    """IP주소 마스킹: 192.168.***.***"""
    first = match.group(1)
    second = match.group(2)
    return f"{first}.{second}.***.***"


# 패턴별 마스킹 함수 매핑
MASK_FUNCTIONS: Dict[str, callable] = {
    "resident_id": _mask_resident_id,
    "foreign_id": _mask_resident_id,  # 동일한 형식
    "passport": _mask_passport,
    "driver_license": _mask_driver_license,
    "phone_mobile": _mask_phone,
    "phone_landline": _mask_phone,
    "email": _mask_email,
    "credit_card": _mask_credit_card,
    "bank_account": _mask_bank_account,
    "ip_address": _mask_ip_address,
}


def mask_pii(text: str, patterns: List[str] = None) -> Tuple[str, List[Dict]]:
    """
    텍스트에서 PII를 감지하고 마스킹

    Args:
        text: 원본 텍스트
        patterns: 적용할 패턴 목록 (None이면 모든 패턴 적용)

    Returns:
        (마스킹된 텍스트, 감지된 PII 정보 리스트)
    """
    if not text:
        return text, []

    detected = []
    masked_text = text

    all_patterns = PIIPatterns.get_all_patterns()

    for pattern_name, pattern, description in all_patterns:
        # 특정 패턴만 적용하는 경우
        if patterns and pattern_name not in patterns:
            continue

        mask_func = MASK_FUNCTIONS.get(pattern_name)
        if not mask_func:
            continue

        # 패턴 매칭 및 마스킹
        matches = list(pattern.finditer(masked_text))
        for match in reversed(matches):  # 뒤에서부터 처리 (인덱스 변경 방지)
            original = match.group(0)
            masked = mask_func(match)

            detected.append({
                "type": pattern_name,
                "description": description,
                "original_length": len(original),
                "position": match.start(),
            })

            masked_text = masked_text[:match.start()] + masked + masked_text[match.end():]

    return masked_text, detected


def contains_pii(text: str) -> bool:
    """
    텍스트에 PII가 포함되어 있는지 확인

    Args:
        text: 검사할 텍스트

    Returns:
        PII 포함 여부
    """
    if not text:
        return False

    for _, pattern, _ in PIIPatterns.get_all_patterns():
        if pattern.search(text):
            return True

    return False
