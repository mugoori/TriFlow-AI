"""
TriFlow AI Backend - FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import logging
import json

from app.config import settings

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

# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Factory Decision Engine - MVP",
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {
        "status": "healthy",
        "checks": {
            "database": "ok",  # TODO: 실제 DB 연결 체크
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


# TODO: 라우터 추가
# from app.routers import agents, tools, bi
# app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
# app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])
# app.include_router(bi.router, prefix="/api/v1/bi", tags=["bi"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
