"""
데이터베이스 초기화 및 시드 데이터 생성
서버 시작 시 호출되어 기본 데이터 설정

Alembic 마이그레이션을 자동으로 실행하여 스키마를 최신 상태로 유지
"""
import os
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Tenant, User
from app.auth.password import get_password_hash
from app.database import engine

logger = logging.getLogger(__name__)

# Alembic 마이그레이션 사용 여부 (기본: True)
USE_ALEMBIC_MIGRATION = os.getenv("USE_ALEMBIC_MIGRATION", "true").lower() == "true"

# 환경변수에서 Admin 계정 정보 로드 (기본값 제공)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@triflow.ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")
DEFAULT_TENANT_NAME = os.getenv("DEFAULT_TENANT_NAME", "Default")


def init_database(db: Session) -> None:
    """
    데이터베이스 초기화

    1. Alembic 마이그레이션 실행 (또는 SQLAlchemy 테이블 생성)
    2. 기본 테넌트 생성
    3. 관리자 계정 생성 (시딩)
    """
    logger.info("Initializing database...")

    try:
        # 0. 스키마 및 테이블 생성
        if USE_ALEMBIC_MIGRATION:
            _run_alembic_migrations()
        else:
            _ensure_tables_exist()

        # 1. 기본 테넌트 생성
        default_tenant = _ensure_default_tenant(db)

        # 2. 관리자 계정 생성
        _ensure_admin_user(db, default_tenant.tenant_id)

        logger.info("Database initialization completed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def _run_alembic_migrations() -> None:
    """
    Alembic 마이그레이션을 프로그래밍 방식으로 실행

    서버 시작 시 자동으로 스키마를 최신 상태로 업그레이드
    """
    try:
        from alembic.config import Config
        from alembic import command

        # alembic.ini 경로 찾기 (backend 디렉토리 기준)
        backend_dir = Path(__file__).resolve().parent.parent
        alembic_ini_path = backend_dir / "alembic.ini"

        if not alembic_ini_path.exists():
            logger.warning(f"alembic.ini not found at {alembic_ini_path}, skipping migration")
            _ensure_tables_exist()
            return

        # Alembic 설정 로드
        alembic_cfg = Config(str(alembic_ini_path))

        # 현재 버전 확인
        logger.info("Checking database migration status...")

        # 마이그레이션 실행 (upgrade head)
        logger.info("Running Alembic migrations...")
        command.upgrade(alembic_cfg, "head")

        logger.info("Database migrations completed successfully")

    except ImportError:
        logger.warning("Alembic not installed, falling back to SQLAlchemy create_all")
        _ensure_tables_exist()
    except Exception as e:
        logger.error(f"Alembic migration failed: {e}")
        logger.warning("Falling back to SQLAlchemy create_all")
        _ensure_tables_exist()


def _ensure_tables_exist() -> None:
    """
    SQLAlchemy 모델 기반 테이블 자동 생성 (Fallback)

    이미 존재하는 테이블은 무시됨 (checkfirst=True가 기본)
    Alembic 마이그레이션을 사용할 수 없을 때 대안으로 사용
    """
    from app.models.core import Base

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created (SQLAlchemy fallback)")
    except Exception as e:
        logger.warning(f"Table creation skipped: {e}")


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
        slug="default",
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
        username="Administrator",
        role="admin",
        is_active=True,
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    logger.info(f"Admin user created: {admin.email}")
    logger.warning(
        "Default admin password is set. "
        "Please change it in production! (ADMIN_PASSWORD env var)"
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
