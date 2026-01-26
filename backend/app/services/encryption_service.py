"""
암호화/복호화 서비스
민감한 데이터 (비밀번호, API Key 등) 보호
"""
import os
import base64
import logging
from cryptography.fernet import Fernet
from typing import Optional

logger = logging.getLogger(__name__)


class EncryptionService:
    """Fernet 대칭키 암호화 서비스"""

    def __init__(self):
        # 환경변수에서 암호화 키 로드
        key = os.getenv("ENCRYPTION_KEY")

        if not key:
            # 개발 환경: 자동 생성 (WARNING 로그)
            key = Fernet.generate_key().decode()
            logger.warning(
                "ENCRYPTION_KEY not found! Using auto-generated key. "
                "This key will change on restart. "
                "Set ENCRYPTION_KEY in production!"
            )

        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        """
        평문 암호화

        Args:
            plaintext: 평문 문자열

        Returns:
            Base64 인코딩된 암호문

        Example:
            >>> encryption = EncryptionService()
            >>> encrypted = encryption.encrypt("MySecret123!")
            >>> encrypted.startswith("gAAAAA")
            True
        """
        if not plaintext:
            return ""

        encrypted = self.fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        암호문 복호화

        Args:
            ciphertext: Base64 인코딩된 암호문

        Returns:
            복호화된 평문

        Raises:
            ValueError: 유효하지 않은 암호문

        Example:
            >>> encryption = EncryptionService()
            >>> encrypted = encryption.encrypt("MySecret123!")
            >>> decrypted = encryption.decrypt(encrypted)
            >>> decrypted
            'MySecret123!'
        """
        if not ciphertext:
            return ""

        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Invalid encrypted data")

    def encrypt_dict(self, data: dict, sensitive_keys: list[str]) -> dict:
        """
        딕셔너리에서 특정 키만 암호화

        Args:
            data: 원본 딕셔너리
            sensitive_keys: 암호화할 키 목록 (예: ["password", "api_key"])

        Returns:
            암호화된 딕셔너리 (원본은 변경되지 않음)

        Example:
            >>> encryption = EncryptionService()
            >>> config = {"host": "db.example.com", "password": "secret"}
            >>> encrypted = encryption.encrypt_dict(config, ["password"])
            >>> encrypted["host"]
            'db.example.com'
            >>> encrypted["password"].startswith("gAAAAA")
            True
        """
        result = data.copy()

        for key in sensitive_keys:
            if key in result and result[key]:
                # 이미 암호화되어 있는지 확인 (Fernet 암호문은 "gAAAAA"로 시작)
                value = str(result[key])
                if not self._is_encrypted(value):
                    result[key] = self.encrypt(value)
                    logger.debug(f"Encrypted key: {key}")

        return result

    def decrypt_dict(self, data: dict, sensitive_keys: list[str]) -> dict:
        """
        딕셔너리에서 특정 키만 복호화

        Args:
            data: 암호화된 딕셔너리
            sensitive_keys: 복호화할 키 목록

        Returns:
            복호화된 딕셔너리 (원본은 변경되지 않음)

        Example:
            >>> encryption = EncryptionService()
            >>> config = {"host": "db.example.com", "password": "secret"}
            >>> encrypted = encryption.encrypt_dict(config, ["password"])
            >>> decrypted = encryption.decrypt_dict(encrypted, ["password"])
            >>> decrypted["password"]
            'secret'
        """
        result = data.copy()

        for key in sensitive_keys:
            if key in result and result[key]:
                try:
                    value = str(result[key])
                    if self._is_encrypted(value):
                        result[key] = self.decrypt(value)
                        logger.debug(f"Decrypted key: {key}")
                except Exception as e:
                    # 복호화 실패 시 원본 유지 (이미 평문일 수 있음)
                    logger.warning(f"Failed to decrypt key '{key}': {e}")

        return result

    def _is_encrypted(self, value: str) -> bool:
        """
        값이 암호화되어 있는지 확인

        Fernet 암호문은 Base64로 인코딩되며 특정 패턴을 가짐
        """
        if not value or not isinstance(value, str):
            return False

        # Fernet 암호문은 base64 인코딩되어 있고, 특정 길이 이상
        # 일반적으로 "gAAAAA"로 시작하는 패턴
        try:
            # Base64 디코딩 가능한지 확인
            decoded = base64.urlsafe_b64decode(value.encode())
            # Fernet 암호문은 최소 57바이트
            return len(decoded) >= 57
        except Exception:
            return False


# Singleton 인스턴스
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    암호화 서비스 싱글톤 인스턴스 반환

    Returns:
        EncryptionService 인스턴스

    Example:
        >>> encryption = get_encryption_service()
        >>> encrypted = encryption.encrypt("password123")
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


# 민감한 필드 목록 (공통 사용)
SENSITIVE_CONFIG_KEYS = [
    "password",
    "api_key",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "ssh_key",
]


def generate_encryption_key() -> str:
    """
    새로운 암호화 키 생성

    Returns:
        Fernet 암호화 키 (Base64 인코딩된 문자열)

    Example:
        >>> key = generate_encryption_key()
        >>> len(key)
        44
    """
    return Fernet.generate_key().decode()
