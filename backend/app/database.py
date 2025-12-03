"""
Database 연결 및 세션 관리
SQLAlchemy를 사용한 DB 세션 팩토리
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# SQLAlchemy Base 클래스
Base = declarative_base()

# Database Engine 생성
engine = create_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # 연결 유효성 체크
    echo=settings.environment == "development",  # 개발 환경에서 SQL 로그 출력
)


# PostgreSQL search_path 설정 (스키마 우선순위)
@event.listens_for(Engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    """
    연결 시 search_path를 설정하여 스키마 우선순위 지정
    core, bi, rag, audit 스키마를 public보다 우선
    SQLite 테스트 환경에서는 건너뜀
    """
    # SQLite doesn't support SET search_path (PostgreSQL only)
    connection_type = type(dbapi_conn).__module__
    if "sqlite" in connection_type.lower():
        return

    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO core, bi, rag, audit, public")
    cursor.close()


# SessionLocal 팩토리
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI Dependency로 사용할 DB 세션 제공

    Usage:
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context Manager로 사용할 DB 세션 제공

    Usage:
        with get_db_context() as db:
            tenants = db.query(Tenant).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    데이터베이스 초기화
    테이블이 없으면 생성 (개발 환경에서만 사용)

    Production에서는 Alembic 마이그레이션 사용
    """
    # 모든 모델을 import해야 Base.metadata에 등록됨
    from app.models import core  # noqa: F401

    # 테이블 생성 (이미 존재하면 무시)
    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    """
    데이터베이스 연결 상태 확인

    Returns:
        연결 성공 시 True, 실패 시 False
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
