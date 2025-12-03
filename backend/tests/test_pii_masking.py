"""
PII 마스킹 유틸리티 테스트
pii_patterns.py의 패턴 매칭 및 마스킹 함수 테스트
"""
import pytest
from app.utils.pii_patterns import (
    PIIPatterns,
    mask_pii,
    contains_pii,
    _mask_resident_id,
    _mask_phone,
    _mask_email,
    _mask_credit_card,
    _mask_bank_account,
    _mask_passport,
    _mask_driver_license,
    _mask_ip_address,
)


class TestPIIPatterns:
    """PII 패턴 정규식 테스트"""

    def test_resident_id_pattern(self):
        """주민등록번호 패턴 테스트"""
        # 유효한 패턴
        assert PIIPatterns.RESIDENT_ID.search("901231-1234567")
        assert PIIPatterns.RESIDENT_ID.search("8506152345678")  # 하이픈 없음
        assert PIIPatterns.RESIDENT_ID.search("생년월일: 850615 2345678")  # 공백 구분

        # 무효한 패턴
        assert not PIIPatterns.RESIDENT_ID.search("123456-1234567")  # 잘못된 월
        assert not PIIPatterns.RESIDENT_ID.search("901231-5234567")  # 5로 시작 (외국인)

    def test_foreign_id_pattern(self):
        """외국인등록번호 패턴 테스트"""
        # 유효한 패턴 (5,6,7,8로 시작)
        assert PIIPatterns.FOREIGN_ID.search("901231-5234567")
        assert PIIPatterns.FOREIGN_ID.search("850615-6345678")
        assert PIIPatterns.FOREIGN_ID.search("750101-7456789")
        assert PIIPatterns.FOREIGN_ID.search("800228-8567890")

        # 무효한 패턴
        assert not PIIPatterns.FOREIGN_ID.search("901231-1234567")  # 1로 시작 (내국인)

    def test_passport_pattern(self):
        """여권번호 패턴 테스트"""
        assert PIIPatterns.PASSPORT.search("M12345678")
        assert PIIPatterns.PASSPORT.search("S98765432")
        assert PIIPatterns.PASSPORT.search("여권번호는 G12345678 입니다")

        # 무효한 패턴
        assert not PIIPatterns.PASSPORT.search("1234567890")  # 알파벳 없음
        assert not PIIPatterns.PASSPORT.search("AB12345678")  # 알파벳 2개

    def test_driver_license_pattern(self):
        """운전면허번호 패턴 테스트"""
        assert PIIPatterns.DRIVER_LICENSE.search("11-22-123456-78")
        assert PIIPatterns.DRIVER_LICENSE.search("1122123456 78")  # 공백 구분
        assert PIIPatterns.DRIVER_LICENSE.search("면허번호: 12-34-567890-12")

    def test_phone_mobile_pattern(self):
        """휴대전화번호 패턴 테스트"""
        assert PIIPatterns.PHONE_MOBILE.search("010-1234-5678")
        assert PIIPatterns.PHONE_MOBILE.search("01012345678")
        assert PIIPatterns.PHONE_MOBILE.search("011-123-4567")
        assert PIIPatterns.PHONE_MOBILE.search("연락처: 010.1234.5678")

        # 무효한 패턴
        assert not PIIPatterns.PHONE_MOBILE.search("020-1234-5678")  # 02로 시작

    def test_phone_landline_pattern(self):
        """일반전화번호 패턴 테스트"""
        assert PIIPatterns.PHONE_LANDLINE.search("02-1234-5678")
        assert PIIPatterns.PHONE_LANDLINE.search("031-123-4567")
        assert PIIPatterns.PHONE_LANDLINE.search("051.1234.5678")

    def test_email_pattern(self):
        """이메일 패턴 테스트"""
        assert PIIPatterns.EMAIL.search("user@example.com")
        assert PIIPatterns.EMAIL.search("test.user+tag@domain.co.kr")
        assert PIIPatterns.EMAIL.search("연락처: admin@triflow.ai 입니다")

        # 무효한 패턴
        assert not PIIPatterns.EMAIL.search("invalid-email")
        assert not PIIPatterns.EMAIL.search("@nodomain.com")

    def test_credit_card_pattern(self):
        """신용카드번호 패턴 테스트"""
        assert PIIPatterns.CREDIT_CARD.search("1234-5678-9012-3456")
        assert PIIPatterns.CREDIT_CARD.search("1234567890123456")
        assert PIIPatterns.CREDIT_CARD.search("카드번호: 1234 5678 9012 3456")

    def test_bank_account_pattern(self):
        """계좌번호 패턴 테스트"""
        assert PIIPatterns.BANK_ACCOUNT.search("123-45-678901")
        assert PIIPatterns.BANK_ACCOUNT.search("1234-56-789012")

    def test_ip_address_pattern(self):
        """IP 주소 패턴 테스트"""
        assert PIIPatterns.IP_ADDRESS.search("192.168.1.1")
        assert PIIPatterns.IP_ADDRESS.search("서버 IP: 10.0.0.1")

    def test_get_all_patterns(self):
        """모든 패턴 조회 테스트"""
        patterns = PIIPatterns.get_all_patterns()
        assert len(patterns) == 10
        assert all(len(p) == 3 for p in patterns)
        pattern_names = [p[0] for p in patterns]
        assert "resident_id" in pattern_names
        assert "email" in pattern_names


class TestMaskFunctions:
    """개별 마스킹 함수 테스트"""

    def test_mask_resident_id(self):
        """주민등록번호 마스킹 테스트"""
        match = PIIPatterns.RESIDENT_ID.search("901231-1234567")
        result = _mask_resident_id(match)
        assert result == "901231-*******"

    def test_mask_phone(self):
        """전화번호 마스킹 테스트"""
        match = PIIPatterns.PHONE_MOBILE.search("010-1234-5678")
        result = _mask_phone(match)
        assert result == "010-****-5678"

    def test_mask_email(self):
        """이메일 마스킹 테스트"""
        match = PIIPatterns.EMAIL.search("user@example.com")
        result = _mask_email(match)
        assert result == "u***@e***.com"

    def test_mask_credit_card(self):
        """신용카드 마스킹 테스트"""
        match = PIIPatterns.CREDIT_CARD.search("1234-5678-9012-3456")
        result = _mask_credit_card(match)
        assert result == "1234-****-****-3456"

    def test_mask_bank_account(self):
        """계좌번호 마스킹 테스트"""
        match = PIIPatterns.BANK_ACCOUNT.search("123-45-678901")
        result = _mask_bank_account(match)
        assert "123-" in result
        assert "01" in result  # 마지막 2자리 유지

    def test_mask_passport(self):
        """여권번호 마스킹 테스트"""
        match = PIIPatterns.PASSPORT.search("M12345678")
        result = _mask_passport(match)
        assert result == "M****5678"

    def test_mask_driver_license(self):
        """운전면허번호 마스킹 테스트"""
        match = PIIPatterns.DRIVER_LICENSE.search("11-22-123456-78")
        result = _mask_driver_license(match)
        assert result == "11-**-******-**"

    def test_mask_ip_address(self):
        """IP 주소 마스킹 테스트"""
        match = PIIPatterns.IP_ADDRESS.search("192.168.1.100")
        result = _mask_ip_address(match)
        assert result == "192.168.***.***"


class TestMaskPII:
    """mask_pii 통합 함수 테스트"""

    def test_mask_single_pii(self):
        """단일 PII 마스킹"""
        text = "제 이메일은 test@example.com 입니다."
        masked, detected = mask_pii(text)

        assert "test@example.com" not in masked
        assert "t***@e***.com" in masked
        assert len(detected) == 1
        assert detected[0]["type"] == "email"

    def test_mask_multiple_pii(self):
        """다중 PII 마스킹"""
        text = "연락처: 010-1234-5678, 이메일: user@test.com"
        masked, detected = mask_pii(text)

        assert "010-1234-5678" not in masked
        assert "user@test.com" not in masked
        assert len(detected) >= 2

    def test_mask_complex_text(self):
        """복잡한 텍스트 마스킹"""
        text = """
        고객 정보:
        - 주민번호: 901231-1234567
        - 전화번호: 010-9876-5432
        - 카드번호: 1234-5678-9012-3456
        - IP: 192.168.0.1
        """
        masked, detected = mask_pii(text)

        assert "901231-1234567" not in masked
        assert "901231-*******" in masked
        assert "010-9876-5432" not in masked
        assert "1234-5678-9012-3456" not in masked
        assert "192.168.0.1" not in masked
        assert len(detected) >= 4

    def test_mask_specific_patterns(self):
        """특정 패턴만 마스킹"""
        text = "이메일: user@test.com, 전화: 010-1234-5678"
        masked, detected = mask_pii(text, patterns=["email"])

        assert "user@test.com" not in masked
        assert "010-1234-5678" in masked  # 전화번호는 그대로
        assert len(detected) == 1

    def test_mask_empty_text(self):
        """빈 텍스트 처리"""
        masked, detected = mask_pii("")
        assert masked == ""
        assert detected == []

    def test_mask_none_text(self):
        """None 입력 처리"""
        masked, detected = mask_pii(None)
        assert masked is None
        assert detected == []

    def test_mask_no_pii(self):
        """PII 없는 텍스트"""
        text = "안녕하세요. 오늘 날씨가 좋습니다."
        masked, detected = mask_pii(text)

        assert masked == text
        assert detected == []


class TestContainsPII:
    """contains_pii 함수 테스트"""

    def test_contains_email(self):
        """이메일 포함 감지"""
        assert contains_pii("연락처: test@example.com")

    def test_contains_phone(self):
        """전화번호 포함 감지"""
        assert contains_pii("전화: 010-1234-5678")

    def test_contains_resident_id(self):
        """주민등록번호 포함 감지"""
        assert contains_pii("주민번호: 901231-1234567")

    def test_contains_credit_card(self):
        """신용카드번호 포함 감지"""
        assert contains_pii("카드: 1234-5678-9012-3456")

    def test_no_pii(self):
        """PII 없음"""
        assert not contains_pii("안녕하세요!")
        assert not contains_pii("오늘 날씨가 좋습니다.")

    def test_empty_text(self):
        """빈 텍스트"""
        assert not contains_pii("")
        assert not contains_pii(None)


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_overlapping_patterns(self):
        """겹치는 패턴 처리"""
        # 전화번호처럼 보이는 숫자열
        text = "코드: 010-1234-5678-9012"
        masked, detected = mask_pii(text)
        # 패턴이 감지되어야 함
        assert len(detected) >= 1

    def test_unicode_text(self):
        """유니코드 텍스트 처리"""
        text = "한글 이름: 홍길동, 이메일: hong@korea.kr"
        masked, detected = mask_pii(text)

        assert "한글 이름: 홍길동" in masked  # 이름은 마스킹 안됨
        assert "hong@korea.kr" not in masked

    def test_special_characters(self):
        """특수문자 포함 텍스트"""
        text = "[연락처] <010-1234-5678> (이메일: test@test.com)"
        masked, detected = mask_pii(text)

        assert "010-1234-5678" not in masked
        assert "test@test.com" not in masked

    def test_multiline_text(self):
        """여러 줄 텍스트"""
        text = """
        첫째 줄: 010-1111-2222
        둘째 줄: user@domain.com
        셋째 줄: 일반 텍스트
        """
        masked, detected = mask_pii(text)

        assert "010-1111-2222" not in masked
        assert "user@domain.com" not in masked
        assert "일반 텍스트" in masked
        assert len(detected) >= 2
