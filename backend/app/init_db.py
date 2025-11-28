"""
데이터베이스 초기화 및 시드 데이터 생성
서버 시작 시 호출되어 기본 데이터 설정
"""
import os
import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Tenant, User
from app.auth.password import get_password_hash

logger = logging.getLogger(__name__)

# 환경변수에서 Admin 계정 정보 로드 (기본값 제공)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@triflow.ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")
DEFAULT_TENANT_NAME = os.getenv("DEFAULT_TENANT_NAME", "Default")


def init_database(db: Session) -> None:
    """
    데이터베이스 초기화

    1. 기본 테넌트 생성
    2. 관리자 계정 생성 (시딩)
    """
    logger.info("Initializing database...")

    try:
        # 1. 기본 테넌트 생성
        default_tenant = _ensure_default_tenant(db)

        # 2. 관리자 계정 생성
        _ensure_admin_user(db, default_tenant.tenant_id)

        logger.info("Database initialization completed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def _ensure_default_tenant(db: Session) -> Tenant:
    """
    기본 테넌트 확인 및 생성

    Returns:
        기본 Tenant 객체
    """
    tenant = db.query(Tenant).filter(Tenant.name == DEFAULT_TENANT_NAME).first()

    if tenant:
        logger.debug(f"Default tenant already exists: {tenant.tenant_id}")
        return tenant

    # 새 테넌트 생성
    tenant = Tenant(
        tenant_id=uuid4(),
        name=DEFAULT_TENANT_NAME,
        description="Default tenant for TriFlow AI MVP",
    )

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    logger.info(f"Default tenant created: {tenant.tenant_id}")
    return tenant


def _ensure_admin_user(db: Session, tenant_id) -> User:
    """
    관리자 계정 확인 및 생성

    Args:
        tenant_id: 관리자가 속할 테넌트 ID

    Returns:
        관리자 User 객체
    """
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()

    if admin:
        logger.debug(f"Admin user already exists: {admin.email}")
        return admin

    # 새 관리자 생성
    admin = User(
        user_id=uuid4(),
        tenant_id=tenant_id,
        email=ADMIN_EMAIL,
        password_hash=get_password_hash(ADMIN_PASSWORD),
        display_name="Administrator",
        role="admin",
        is_active=True,
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    logger.info(f"Admin user created: {admin.email}")
    logger.warning(
        f"Default admin password is set. "
        f"Please change it in production! (ADMIN_PASSWORD env var)"
    )

    return admin


def seed_sample_data(db: Session) -> None:
    """
    샘플 데이터 시딩 (개발/테스트용)

    환경변수 SEED_SAMPLE_DATA=true 일 때만 실행
    """
    if os.getenv("SEED_SAMPLE_DATA", "").lower() != "true":
        return

    logger.info("Seeding sample data...")

    # 추가 샘플 데이터는 여기에 구현
    # 예: 샘플 워크플로우, 룰셋 등

    logger.info("Sample data seeding completed")
