# ===================================================
# TriFlow AI - System Settings Service
# 시스템 설정 관리 (암호화 저장, DB 우선 조회)
# ===================================================

import base64
import logging
import os
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    AES-256 기반 암호화 서비스
    SECRET_KEY를 기반으로 Fernet 대칭키 생성
    """

    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._init_encryption()

    def _init_encryption(self):
        """암호화 키 초기화"""
        from app.config import settings

        secret_key = settings.secret_key
        if not secret_key or secret_key == "your_secret_key_here_change_in_production":
            logger.warning("SECRET_KEY가 기본값입니다. 프로덕션에서는 변경하세요.")
            secret_key = "triflow-default-key-change-me"

        # PBKDF2로 32바이트 키 생성
        salt = b"triflow-ai-salt-v1"  # 고정 salt (키 재생성 방지)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """문자열 암호화 → base64 인코딩된 암호문"""
        if not plaintext:
            return ""
        encrypted = self._fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, ciphertext: str) -> str:
        """base64 암호문 복호화 → 평문"""
        if not ciphertext:
            return ""
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"복호화 실패: {e}")
            return ""

    def mask_value(self, value: str, visible_chars: int = 4) -> str:
        """
        민감 정보 마스킹
        예: "sk-abc123xyz789" → "sk-a...9789"
        """
        if not value or len(value) <= visible_chars * 2:
            return "****"
        return f"{value[:visible_chars]}...{value[-visible_chars:]}"


# 싱글톤 인스턴스
encryption_service = EncryptionService()


# 설정 키 정의 (민감 여부 포함)
SETTING_DEFINITIONS = {
    # Slack
    "slack_webhook_url": {"category": "notification", "sensitive": True, "label": "Slack Webhook URL"},
    "slack_default_channel": {"category": "notification", "sensitive": False, "label": "Slack 기본 채널"},
    # Email (SMTP)
    "smtp_host": {"category": "notification", "sensitive": False, "label": "SMTP 호스트"},
    "smtp_port": {"category": "notification", "sensitive": False, "label": "SMTP 포트"},
    "smtp_user": {"category": "notification", "sensitive": False, "label": "SMTP 사용자"},
    "smtp_password": {"category": "notification", "sensitive": True, "label": "SMTP 비밀번호"},
    "smtp_from": {"category": "notification", "sensitive": False, "label": "발신자 이메일"},
    "smtp_use_tls": {"category": "notification", "sensitive": False, "label": "TLS 사용"},
    # AWS S3
    "aws_region": {"category": "storage", "sensitive": False, "label": "AWS 리전"},
    "aws_access_key_id": {"category": "storage", "sensitive": True, "label": "AWS Access Key"},
    "aws_secret_access_key": {"category": "storage", "sensitive": True, "label": "AWS Secret Key"},
    "s3_bucket_name": {"category": "storage", "sensitive": False, "label": "S3 버킷명"},
    # AI
    "anthropic_api_key": {"category": "ai", "sensitive": True, "label": "Anthropic API Key"},
    # AI Model Settings (기본 모델 + 기능별 오버라이드)
    "default_llm_model": {
        "category": "ai",
        "sensitive": False,
        "label": "기본 LLM 모델",
        "default": "claude-sonnet-4-5-20250929"
    },
    "meta_router_model": {
        "category": "ai",
        "sensitive": False,
        "label": "Meta Router 모델",
        "default": ""  # 비어있으면 default_llm_model 사용
    },
    "bi_planner_model": {
        "category": "ai",
        "sensitive": False,
        "label": "BI Planner 모델",
        "default": ""
    },
    "workflow_planner_model": {
        "category": "ai",
        "sensitive": False,
        "label": "Workflow Planner 모델",
        "default": ""
    },
    "judgment_agent_model": {
        "category": "ai",
        "sensitive": False,
        "label": "Judgment Agent 모델",
        "default": ""
    },
    "learning_agent_model": {
        "category": "ai",
        "sensitive": False,
        "label": "Learning Agent 모델",
        "default": ""
    },
    # Learning Pipeline
    "learning_min_quality_score": {"category": "learning", "sensitive": False, "label": "최소 품질 점수"},
    "learning_auto_extract_enabled": {"category": "learning", "sensitive": False, "label": "자동 추출 활성화"},
    "learning_auto_extract_interval_hours": {"category": "learning", "sensitive": False, "label": "추출 주기(시간)"},
    "learning_max_tree_depth": {"category": "learning", "sensitive": False, "label": "최대 트리 깊이"},
    "learning_min_samples_split": {"category": "learning", "sensitive": False, "label": "최소 분할 샘플"},
    "learning_golden_set_auto_update": {"category": "learning", "sensitive": False, "label": "골든셋 자동 업데이트"},
    "learning_golden_set_threshold": {"category": "learning", "sensitive": False, "label": "골든셋 임계값"},
}


class SystemSettingsService:
    """
    시스템 설정 관리 서비스
    - DB에 암호화하여 저장
    - 조회 시 DB 우선, 없으면 환경변수 fallback
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_loaded = False

    def _ensure_table(self, db) -> None:
        """system_settings 테이블 생성 (없으면)"""
        from sqlalchemy import text

        create_sql = text("""
            CREATE TABLE IF NOT EXISTS core.system_settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                is_encrypted BOOLEAN DEFAULT FALSE,
                category VARCHAR(50),
                updated_at TIMESTAMP DEFAULT NOW(),
                updated_by VARCHAR(100)
            )
        """)
        db.execute(create_sql)
        db.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        설정 값 조회 (DB 우선 → 환경변수 fallback)
        """
        from app.database import get_db_context
        from sqlalchemy import text

        # 1. DB에서 조회
        try:
            with get_db_context() as db:
                self._ensure_table(db)

                result = db.execute(
                    text("SELECT value, is_encrypted FROM core.system_settings WHERE key = :key"),
                    {"key": key}
                ).fetchone()

                if result:
                    value, is_encrypted = result
                    if is_encrypted and value:
                        return encryption_service.decrypt(value)
                    return value
        except Exception as e:
            logger.warning(f"DB 설정 조회 실패 ({key}): {e}")

        # 2. 환경변수 fallback
        env_key = key.upper()
        env_value = os.getenv(env_key)
        if env_value:
            return env_value

        return default

    def get_setting_with_scope(
        self,
        key: str,
        tenant_id: Optional[str] = None,
        default: Optional[str] = None
    ) -> Optional[str]:
        """
        계층적 설정 조회: Tenant → Global (DB) → Environment → Default

        Multi-Tenant 환경에서 테넌트별 설정을 우선 적용하고,
        없으면 글로벌 설정, 환경변수, 기본값 순으로 fallback.

        Args:
            key: 설정 키
            tenant_id: 테넌트 ID (UUID 문자열)
            default: 기본값

        Returns:
            설정 값 또는 None
        """
        from app.database import get_db_context
        from sqlalchemy import text

        # 1. Tenant 설정 확인 (tenant_id가 있는 경우)
        if tenant_id:
            try:
                with get_db_context() as db:
                    result = db.execute(
                        text("""
                            SELECT settings FROM core.tenants
                            WHERE tenant_id = :tenant_id
                        """),
                        {"tenant_id": tenant_id}
                    ).fetchone()

                    if result and result[0]:
                        tenant_settings = result[0]
                        if isinstance(tenant_settings, dict) and key in tenant_settings:
                            logger.debug(f"설정 '{key}' tenant 스코프에서 조회됨")
                            return tenant_settings[key]
            except Exception as e:
                logger.warning(f"Tenant 설정 조회 실패 ({key}, tenant={tenant_id}): {e}")

        # 2. Global DB 설정 확인
        try:
            with get_db_context() as db:
                self._ensure_table(db)

                result = db.execute(
                    text("SELECT value, is_encrypted FROM core.system_settings WHERE key = :key"),
                    {"key": key}
                ).fetchone()

                if result:
                    value, is_encrypted = result
                    if is_encrypted and value:
                        logger.debug(f"설정 '{key}' global DB 스코프에서 조회됨 (암호화)")
                        return encryption_service.decrypt(value)
                    if value:
                        logger.debug(f"설정 '{key}' global DB 스코프에서 조회됨")
                        return value
        except Exception as e:
            logger.warning(f"Global DB 설정 조회 실패 ({key}): {e}")

        # 3. Environment 확인
        env_key = key.upper()
        env_value = os.getenv(env_key)
        if env_value:
            logger.debug(f"설정 '{key}' 환경변수에서 조회됨")
            return env_value

        # 4. 정의된 기본값 확인
        definition = SETTING_DEFINITIONS.get(key, {})
        defined_default = definition.get("default")
        if defined_default is not None:
            logger.debug(f"설정 '{key}' 정의된 기본값 사용")
            return defined_default

        # 5. 파라미터 기본값 반환
        return default

    def set_tenant_setting(
        self,
        tenant_id: str,
        key: str,
        value: Any,
        updated_by: str = "system"
    ) -> bool:
        """
        테넌트별 설정 저장 (tenants.settings JSONB 필드에 저장)

        Args:
            tenant_id: 테넌트 ID (UUID 문자열)
            key: 설정 키
            value: 설정 값
            updated_by: 업데이트한 사용자

        Returns:
            성공 여부
        """
        from app.database import get_db_context
        from sqlalchemy import text

        try:
            with get_db_context() as db:
                # JSONB 필드 업데이트 (기존 설정에 병합)
                update_sql = text("""
                    UPDATE core.tenants
                    SET settings = COALESCE(settings, '{}'::jsonb) || :new_setting::jsonb,
                        updated_at = NOW()
                    WHERE tenant_id = :tenant_id
                """)
                import json
                result = db.execute(update_sql, {
                    "tenant_id": tenant_id,
                    "new_setting": json.dumps({key: value}),
                })
                db.commit()

                if result.rowcount > 0:
                    logger.info(f"Tenant 설정 저장: {key} (tenant={tenant_id}, by {updated_by})")
                    return True
                else:
                    logger.warning(f"Tenant를 찾을 수 없음: {tenant_id}")
                    return False

        except Exception as e:
            logger.error(f"Tenant 설정 저장 실패 ({key}, tenant={tenant_id}): {e}")
            return False

    def delete_tenant_setting(
        self,
        tenant_id: str,
        key: str
    ) -> bool:
        """
        테넌트별 설정 삭제 (글로벌 설정으로 fallback)

        Args:
            tenant_id: 테넌트 ID (UUID 문자열)
            key: 삭제할 설정 키

        Returns:
            성공 여부
        """
        from app.database import get_db_context
        from sqlalchemy import text

        try:
            with get_db_context() as db:
                # JSONB에서 특정 키 삭제
                update_sql = text("""
                    UPDATE core.tenants
                    SET settings = settings - :key,
                        updated_at = NOW()
                    WHERE tenant_id = :tenant_id
                """)
                result = db.execute(update_sql, {
                    "tenant_id": tenant_id,
                    "key": key,
                })
                db.commit()

                if result.rowcount > 0:
                    logger.info(f"Tenant 설정 삭제: {key} (tenant={tenant_id})")
                    return True
                else:
                    logger.warning(f"Tenant를 찾을 수 없음: {tenant_id}")
                    return False

        except Exception as e:
            logger.error(f"Tenant 설정 삭제 실패 ({key}, tenant={tenant_id}): {e}")
            return False

    def get_tenant_settings(self, tenant_id: str) -> Dict[str, Any]:
        """
        테넌트의 모든 커스텀 설정 조회

        Args:
            tenant_id: 테넌트 ID (UUID 문자열)

        Returns:
            테넌트 설정 딕셔너리
        """
        from app.database import get_db_context
        from sqlalchemy import text

        try:
            with get_db_context() as db:
                result = db.execute(
                    text("SELECT settings FROM core.tenants WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id}
                ).fetchone()

                if result and result[0]:
                    return result[0]
                return {}

        except Exception as e:
            logger.warning(f"Tenant 설정 조회 실패 (tenant={tenant_id}): {e}")
            return {}

    def set_setting(
        self,
        key: str,
        value: str,
        updated_by: str = "system"
    ) -> bool:
        """
        설정 값 저장 (민감 정보는 암호화)
        """
        from app.database import get_db_context
        from sqlalchemy import text

        definition = SETTING_DEFINITIONS.get(key, {})
        is_sensitive = definition.get("sensitive", False)
        category = definition.get("category", "general")

        # 민감 정보 암호화
        stored_value = value
        if is_sensitive and value:
            stored_value = encryption_service.encrypt(value)

        try:
            with get_db_context() as db:
                self._ensure_table(db)

                # UPSERT
                upsert_sql = text("""
                    INSERT INTO core.system_settings (key, value, is_encrypted, category, updated_at, updated_by)
                    VALUES (:key, :value, :is_encrypted, :category, NOW(), :updated_by)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        is_encrypted = EXCLUDED.is_encrypted,
                        category = EXCLUDED.category,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """)
                db.execute(upsert_sql, {
                    "key": key,
                    "value": stored_value,
                    "is_encrypted": is_sensitive,
                    "category": category,
                    "updated_by": updated_by,
                })
                db.commit()

            logger.info(f"설정 저장: {key} (by {updated_by})")
            return True

        except Exception as e:
            logger.error(f"설정 저장 실패 ({key}): {e}")
            return False

    def delete_setting(self, key: str) -> bool:
        """설정 삭제 (환경변수 fallback으로 복귀)"""
        from app.database import get_db_context
        from sqlalchemy import text

        try:
            with get_db_context() as db:
                db.execute(
                    text("DELETE FROM core.system_settings WHERE key = :key"),
                    {"key": key}
                )
                db.commit()
            logger.info(f"설정 삭제: {key}")
            return True
        except Exception as e:
            logger.error(f"설정 삭제 실패 ({key}): {e}")
            return False

    def get_all_settings(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        모든 설정 조회 (민감 정보는 마스킹)
        """
        from app.database import get_db_context
        from sqlalchemy import text

        results = []

        try:
            with get_db_context() as db:
                self._ensure_table(db)

                if category:
                    rows = db.execute(
                        text("SELECT key, value, is_encrypted, category, updated_at FROM core.system_settings WHERE category = :category"),
                        {"category": category}
                    ).fetchall()
                else:
                    rows = db.execute(
                        text("SELECT key, value, is_encrypted, category, updated_at FROM core.system_settings")
                    ).fetchall()

                db_keys = set()
                for row in rows:
                    key, value, is_encrypted, cat, updated_at = row
                    db_keys.add(key)

                    definition = SETTING_DEFINITIONS.get(key, {})
                    is_sensitive = definition.get("sensitive", False)

                    # 값 처리
                    display_value = None
                    if value:
                        if is_encrypted:
                            decrypted = encryption_service.decrypt(value)
                            display_value = encryption_service.mask_value(decrypted) if is_sensitive else decrypted
                        else:
                            display_value = encryption_service.mask_value(value) if is_sensitive else value

                    results.append({
                        "key": key,
                        "value": display_value,
                        "is_set": bool(value),
                        "source": "database",
                        "category": cat,
                        "label": definition.get("label", key),
                        "sensitive": is_sensitive,
                        "updated_at": updated_at.isoformat() if updated_at else None,
                    })

        except Exception as e:
            logger.warning(f"DB 설정 목록 조회 실패: {e}")

        # 정의된 설정 중 DB에 없는 것은 환경변수에서 확인
        for key, definition in SETTING_DEFINITIONS.items():
            if category and definition.get("category") != category:
                continue
            if key in [r["key"] for r in results]:
                continue

            env_key = key.upper()
            env_value = os.getenv(env_key)
            default_value = definition.get("default")

            is_sensitive = definition.get("sensitive", False)
            display_value = None
            source = "not_set"
            is_set = False

            if env_value:
                display_value = encryption_service.mask_value(env_value) if is_sensitive else env_value
                source = "environment"
                is_set = True
            elif default_value:
                # 정의된 기본값 사용
                display_value = default_value
                source = "default"
                is_set = False  # 기본값은 "설정됨"이 아님

            results.append({
                "key": key,
                "value": display_value,
                "is_set": is_set,
                "source": source,
                "category": definition.get("category", "general"),
                "label": definition.get("label", key),
                "sensitive": is_sensitive,
                "updated_at": None,
            })

        return results

    def test_notification_settings(self) -> Dict[str, Any]:
        """알림 설정 테스트 결과"""
        slack_url = self.get_setting("slack_webhook_url")
        smtp_host = self.get_setting("smtp_host")
        smtp_user = self.get_setting("smtp_user")
        smtp_password = self.get_setting("smtp_password")

        return {
            "slack": {
                "configured": bool(slack_url),
                "webhook_url_set": bool(slack_url),
            },
            "email": {
                "configured": bool(smtp_host and smtp_user and smtp_password),
                "smtp_host": smtp_host or "미설정",
                "smtp_user_set": bool(smtp_user),
                "smtp_password_set": bool(smtp_password),
            },
        }


# 싱글톤 인스턴스
settings_service = SystemSettingsService()
