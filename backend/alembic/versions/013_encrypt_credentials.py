"""Encrypt existing credentials in data_sources

Revision ID: 013_encrypt_credentials
Revises: 012_prompt_metrics
Create Date: 2026-01-22

이 Migration은 기존 평문으로 저장된 자격증명을 암호화합니다.
- core.data_sources 테이블의 connection_config JSONB 필드 내 민감 정보 암호화
- 암호화 대상: password, api_key, secret, token 등

주의사항:
1. ENCRYPTION_KEY 환경변수가 설정되어 있어야 합니다.
2. 이 Migration은 되돌릴 수 없습니다(downgrade 불가).
3. 실행 전 DB 백업을 권장합니다.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
import os
import sys
import json

# revision identifiers, used by Alembic.
revision = '013_encrypt_credentials'
down_revision = '012_prompt_metrics'
branch_labels = None
depends_on = None


def upgrade():
    """기존 평문 데이터를 암호화"""

    # Python path 설정 (app 모듈 import를 위해)
    from pathlib import Path
    backend_path = Path(__file__).parent.parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    # 암호화 서비스 import
    try:
        from app.services.encryption_service import get_encryption_service, SENSITIVE_CONFIG_KEYS
    except ImportError as e:
        print(f"❌ Error: Cannot import encryption service: {e}")
        print("Make sure ENCRYPTION_KEY is set in your environment.")
        raise

    # 환경변수 확인
    if not os.getenv("ENCRYPTION_KEY"):
        raise ValueError(
            "ENCRYPTION_KEY environment variable is not set!\n"
            "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "Then set it: export ENCRYPTION_KEY='your-generated-key'"
        )

    encryption = get_encryption_service()

    # DB 연결
    conn = op.get_bind()

    # 1. core.data_sources 테이블 업데이트
    print("📊 Encrypting credentials in core.data_sources...")

    # 모든 DataSource 조회
    result = conn.execute(text("""
        SELECT source_id, connection_config
        FROM core.data_sources
        WHERE connection_config IS NOT NULL
    """))

    encrypted_count = 0
    skipped_count = 0

    for row in result:
        source_id = row[0]
        config = row[1]  # JSONB는 자동으로 dict로 변환됨

        if not config:
            skipped_count += 1
            continue

        # 민감한 키가 있는지 확인
        has_sensitive_data = any(
            key in config and config[key]
            for key in SENSITIVE_CONFIG_KEYS
        )

        if not has_sensitive_data:
            skipped_count += 1
            continue

        # 이미 암호화되어 있는지 확인 (Fernet 암호문은 "gAAAAA"로 시작)
        already_encrypted = False
        for key in SENSITIVE_CONFIG_KEYS:
            if key in config and config[key]:
                value = str(config[key])
                # Base64로 인코딩된 Fernet 암호문인지 확인
                if encryption._is_encrypted(value):
                    already_encrypted = True
                    break

        if already_encrypted:
            print(f"  ⏭️  Skipping {source_id} (already encrypted)")
            skipped_count += 1
            continue

        # 암호화 수행
        try:
            encrypted_config = encryption.encrypt_dict(config, SENSITIVE_CONFIG_KEYS)

            # DB 업데이트
            conn.execute(
                text("""
                    UPDATE core.data_sources
                    SET connection_config = :config
                    WHERE source_id = :id
                """),
                {"config": json.dumps(encrypted_config), "id": source_id}
            )

            encrypted_count += 1
            print(f"  ✅ Encrypted credentials for source_id: {source_id}")

        except Exception as e:
            print(f"  ⚠️  Failed to encrypt {source_id}: {e}")
            # 개별 항목 실패는 계속 진행
            skipped_count += 1
            continue

    print(f"\n✅ Migration completed:")
    print(f"   - Encrypted: {encrypted_count} sources")
    print(f"   - Skipped: {skipped_count} sources")

    # 2. 향후 DataConnector 테이블도 추가 가능
    # (현재는 사용되지 않음)


def downgrade():
    """
    ⚠️ 복호화는 보안상 지원하지 않습니다.

    암호화된 데이터를 평문으로 되돌리는 것은 보안 리스크이므로,
    downgrade는 의도적으로 구현하지 않았습니다.

    만약 정말 필요하다면, 수동으로 복호화 스크립트를 실행하세요:

    from app.services.encryption_service import get_encryption_service
    encryption = get_encryption_service()
    # ... 수동 복호화 로직
    """
    raise NotImplementedError(
        "Downgrade is not supported for security reasons. "
        "Encrypted credentials cannot be automatically decrypted."
    )
