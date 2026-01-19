"""AWS Secrets Manager 클라이언트

데이터베이스 비밀번호, API 키 등 민감한 정보를 안전하게 관리합니다.
캐싱을 통해 API 호출을 최소화합니다.
"""

import json
import logging
from functools import lru_cache
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError

try:
    import boto3
    SECRETS_MANAGER_AVAILABLE = True
except ImportError:
    SECRETS_MANAGER_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class SecretsManagerClient:
    """Secrets Manager 클라이언트

    사용 예시:
        sm_client = SecretsManagerClient()
        db_secret = sm_client.get_secret("triflow/prod/database")
        db_password = db_secret.get("password")
    """

    def __init__(self):
        if not SECRETS_MANAGER_AVAILABLE:
            logger.warning("boto3 not installed, Secrets Manager disabled")
            self.client = None
            return

        try:
            self.client = boto3.client(
                'secretsmanager',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id if settings.aws_access_key_id else None,
                aws_secret_access_key=settings.aws_secret_access_key if settings.aws_secret_access_key else None
            )
            logger.info("Secrets Manager client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Secrets Manager client: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Secrets Manager 사용 가능 여부"""
        return self.client is not None

    @lru_cache(maxsize=128)
    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """Secret 값 조회 (캐싱됨)

        Args:
            secret_name: Secret 이름 (예: triflow/prod/database)

        Returns:
            Secret 값 (JSON 파싱됨) 또는 빈 dict

        Note:
            - LRU 캐시로 같은 secret은 재사용
            - Secrets Manager 실패 시 빈 dict 반환 (Fallback)
        """
        if not self.is_available():
            logger.warning(f"Secrets Manager not available, returning empty dict for {secret_name}")
            return {}

        try:
            response = self.client.get_secret_value(SecretId=secret_name)

            # SecretString 파싱
            if 'SecretString' in response:
                secret = json.loads(response['SecretString'])
                logger.debug(f"Retrieved secret: {secret_name}")
                return secret
            else:
                # Binary secret (사용하지 않음)
                logger.warning(f"Binary secret not supported: {secret_name}")
                return {}

        except ClientError as e:
            error_code = e.response['Error']['Code']

            if error_code == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {secret_name}")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid secret request: {secret_name}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter: {secret_name}")
            elif error_code == 'DecryptionFailure':
                logger.error(f"Decryption failed: {secret_name}")
            elif error_code == 'InternalServiceError':
                logger.error(f"Secrets Manager internal error: {secret_name}")
            else:
                logger.error(f"Secrets Manager error ({error_code}): {secret_name}")

            # Fallback to environment variables
            logger.info(f"Falling back to environment variables for {secret_name}")
            return {}

        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            return {}

    def get_secret_value(self, secret_name: str, key: str, default: Optional[str] = None) -> Optional[str]:
        """Secret에서 특정 키 값 조회

        Args:
            secret_name: Secret 이름
            key: JSON 키
            default: 기본값 (없을 경우)

        Returns:
            Secret 값 또는 기본값
        """
        secret = self.get_secret(secret_name)
        return secret.get(key, default)

    def create_secret(self, secret_name: str, secret_value: Dict[str, Any]) -> bool:
        """새 Secret 생성

        Args:
            secret_name: Secret 이름
            secret_value: Secret 값 (dict)

        Returns:
            성공 여부
        """
        if not self.is_available():
            logger.warning("Secrets Manager not available")
            return False

        try:
            self.client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_value),
                Description=f"TriFlow AI secret: {secret_name}"
            )
            logger.info(f"Created secret: {secret_name}")
            return True

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceExistsException':
                logger.warning(f"Secret already exists: {secret_name}")
            else:
                logger.error(f"Failed to create secret ({error_code}): {secret_name}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating secret: {e}")
            return False

    def update_secret(self, secret_name: str, secret_value: Dict[str, Any]) -> bool:
        """기존 Secret 업데이트

        Args:
            secret_name: Secret 이름
            secret_value: 새 Secret 값 (dict)

        Returns:
            성공 여부
        """
        if not self.is_available():
            logger.warning("Secrets Manager not available")
            return False

        try:
            self.client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_value)
            )

            # 캐시 무효화 (업데이트 후 새 값 가져오기)
            self.get_secret.cache_clear()

            logger.info(f"Updated secret: {secret_name}")
            return True

        except ClientError as e:
            logger.error(f"Failed to update secret: {secret_name} - {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating secret: {e}")
            return False

    def delete_secret(self, secret_name: str, recovery_window_days: int = 30) -> bool:
        """Secret 삭제 (복구 기간 포함)

        Args:
            secret_name: Secret 이름
            recovery_window_days: 복구 가능 기간 (기본 30일)

        Returns:
            성공 여부
        """
        if not self.is_available():
            logger.warning("Secrets Manager not available")
            return False

        try:
            self.client.delete_secret(
                SecretId=secret_name,
                RecoveryWindowInDays=recovery_window_days
            )

            # 캐시 무효화
            self.get_secret.cache_clear()

            logger.info(f"Deleted secret (recovery window: {recovery_window_days} days): {secret_name}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete secret: {secret_name} - {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting secret: {e}")
            return False


# 싱글톤 인스턴스 (모듈 로드 시 1회만 생성)
_secrets_manager_client: Optional[SecretsManagerClient] = None


def get_secrets_manager_client() -> SecretsManagerClient:
    """Secrets Manager 클라이언트 싱글톤 인스턴스 반환"""
    global _secrets_manager_client

    if _secrets_manager_client is None:
        _secrets_manager_client = SecretsManagerClient()

    return _secrets_manager_client
