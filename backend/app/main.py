"""
TriFlow AI Backend - FastAPI Main Application
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import logging

from app.config import settings
from app.database import check_db_connection, SessionLocal

# 로깅 설정
if settings.log_format == "json":
    logging.basicConfig(
        level=settings.log_level,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    )
else:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 시작/종료 시 실행되는 이벤트
    - 시작: DB 초기화, Admin 계정 시딩
    - 종료: 리소스 정리
    """
    # Startup
    logger.info("Starting TriFlow AI Backend...")

    # DB 초기화 (Admin 계정 시딩 포함)
    try:
        from app.init_db import init_database, seed_sample_data

        db = SessionLocal()
        try:
            init_database(db)
            seed_sample_data(db)
        finally:
            db.close()

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down TriFlow AI Backend...")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Factory Decision Engine - MVP",
    lifespan=lifespan,
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PII 마스킹 미들웨어 (환경변수로 활성화 제어)
PII_MASKING_ENABLED = os.getenv("PII_MASKING_ENABLED", "true").lower() == "true"
if PII_MASKING_ENABLED:
    try:
        from app.middleware.pii_masking import PIIMaskingMiddleware

        app.add_middleware(
            PIIMaskingMiddleware,
            enabled=True,
            mask_request=True,
            mask_response=True,
            target_paths=["/api/v1/agents/"],
            exclude_paths=["/health", "/docs", "/redoc", "/openapi.json", "/api/v1/auth/"],
        )
        logger.info("PII Masking middleware enabled")
    except Exception as e:
        logger.warning(f"Failed to enable PII Masking middleware: {e}")
else:
    logger.info("PII Masking middleware disabled")

# Prometheus 메트릭 엔드포인트
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "ok",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    db_status = "ok" if check_db_connection() else "error"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "checks": {
            "database": db_status,
            "redis": "ok",  # TODO: 실제 Redis 연결 체크
        }
    }


@app.get("/api/v1/info")
async def api_info():
    """API 정보"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "llm_model": settings.default_llm_model,
        "environment": settings.environment,
    }


# ========== 라우터 등록 ==========

# Tenants 라우터
from app.routers import tenants
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])

# Auth 라우터 (Public - 인증 불필요)
try:
    from app.routers import auth
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    logger.info("Auth router registered")
except Exception as e:
    logger.error(f"Failed to register auth router: {e}")

# Agent 라우터
from app.routers import agents
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])

# Sensors 라우터
try:
    from app.routers import sensors
    app.include_router(sensors.router, prefix="/api/v1/sensors", tags=["sensors"])
    logger.info("Sensors router registered")
except Exception as e:
    logger.error(f"Failed to register sensors router: {e}")

# Workflows 라우터
try:
    from app.routers import workflows
    app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
    logger.info("Workflows router registered")
except Exception as e:
    logger.error(f"Failed to register workflows router: {e}")

# Rulesets 라우터
try:
    from app.routers import rulesets
    app.include_router(rulesets.router, prefix="/api/v1/rulesets", tags=["rulesets"])
    logger.info("Rulesets router registered")
except Exception as e:
    logger.error(f"Failed to register rulesets router: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
