"""
Password 유틸리티 테스트
app/auth/password.py의 비밀번호 해싱/검증 테스트
"""
import pytest

from app.auth.password import verify_password, get_password_hash


class TestGetPasswordHash:
    """get_password_hash 함수 테스트"""

    def test_hash_password(self):
        """비밀번호 해시 생성"""
        password = "secure_password123"

        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        # bcrypt 해시는 $2b$로 시작
        assert hashed.startswith("$2")

    def test_hash_different_each_time(self):
        """같은 비밀번호도 매번 다른 해시 생성 (salt)"""
        password = "same_password"

        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2

    def test_hash_unicode_password(self):
        """유니코드 비밀번호 해시"""
        password = "비밀번호123"

        hashed = get_password_hash(password)

        assert hashed.startswith("$2")


class TestVerifyPassword:
    """verify_password 함수 테스트"""

    def test_verify_correct_password(self):
        """올바른 비밀번호 검증 성공"""
        password = "correct_password"
        hashed = get_password_hash(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_wrong_password(self):
        """틀린 비밀번호 검증 실패"""
        password = "correct_password"
        hashed = get_password_hash(password)

        result = verify_password("wrong_password", hashed)

        assert result is False

    def test_verify_unicode_password(self):
        """유니코드 비밀번호 검증"""
        password = "비밀번호123"
        hashed = get_password_hash(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_empty_password(self):
        """빈 비밀번호"""
        password = ""
        hashed = get_password_hash(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_long_password(self):
        """긴 비밀번호"""
        password = "a" * 100
        hashed = get_password_hash(password)

        result = verify_password(password, hashed)

        assert result is True
