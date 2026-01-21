"""
TriFlow AI Backend - FastAPI Main Application
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.exceptions import RequestValidationError
from prometheus_client import make_asgi_app
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

# Sentry 초기화 (가장 먼저 실행되어야 함)
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.config import settings

# Sentry 설정
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"triflow-ai@{settings.app_version}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        # PII 필터링
        send_default_pii=False,
        # 성능 영향 최소화
        attach_stacktrace=True,
        # 에러 샘플링
        sample_rate=1.0,
    )
from app.utils.errors import classify_error, format_error_response, ErrorCategory
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


async def warmup_agents():
    """에이전트 사전 초기화 - 첫 요청 지연 방지"""
    import asyncio
    from functools import partial
    from concurrent.futures import ThreadPoolExecutor

    try:
        from app.services.agent_orchestrator import orchestrator

        # ThreadPoolExecutor로 동기 함수 실행
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)

        # 간단한 워밍업 요청 (LLM API 호출 포함)
        await loop.run_in_executor(
            executor,
            partial(
                orchestrator.process,
                message="시스템 워밍업",
                context={"warmup": True},
                tenant_id=None,
            )
        )
        executor.shutdown(wait=False)
    except Exception as e:
        logger.warning(f"Agent warmup failed (non-critical): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 시작/종료 시 실행되는 이벤트
    - 시작: DB 초기화, Admin 계정 시딩, 에이전트 워밍업
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

    # 에이전트 워밍업 (첫 요청 지연 방지)
    logger.info("Warming up agents...")
    await warmup_agents()
    logger.info("Agents warmed up successfully")

    # Materialized Views 워밍업 (첫 대시보드 쿼리 성능 향상)
    try:
        from app.services.mv_refresh_service import mv_refresh_service
        from app.database import async_session_factory

        logger.info("Warming up Materialized Views...")
        async with async_session_factory() as db:
            result = await mv_refresh_service.refresh_all(db)
            if result["success"]:
                logger.info(f"MV warm-up completed: {len(result['views'])} views refreshed")
            else:
                logger.warning(f"MV warm-up completed with errors: {result['errors']}")
    except Exception as e:
        logger.warning(f"MV warm-up failed (non-critical): {e}")

    # Canary 모니터 태스크 시작
    try:
        from app.tasks.canary_monitor_task import start_monitor
        start_monitor()
        logger.info("Canary monitor task started")
    except Exception as e:
        logger.warning(f"Canary monitor task failed to start: {e}")

    # 스케줄러 시작 (MV 리프레시 포함)
    try:
        from app.services.scheduler_service import scheduler
        await scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")

    yield

    # Shutdown
    logger.info("Shutting down TriFlow AI Backend...")

    # 스케줄러 중지
    try:
        from app.services.scheduler_service import scheduler
        await scheduler.stop()
        logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.warning(f"Scheduler failed to stop: {e}")

    # Canary 모니터 태스크 중지
    try:
        from app.tasks.canary_monitor_task import stop_monitor
        stop_monitor()
        logger.info("Canary monitor task stopped")
    except Exception as e:
        logger.warning(f"Canary monitor task failed to stop: {e}")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Factory Decision Engine - MVP",
    lifespan=lifespan,
)

# ========== 파일 업로드 크기 제한 설정 ==========
# 모듈 ZIP 파일 업로드를 위해 200MB까지 허용
from starlette.middleware.base import BaseHTTPMiddleware

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request, call_next):
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_body_size:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"File too large (max {self.max_body_size // 1024 // 1024}MB)"}
                )
        return await call_next(request)

app.add_middleware(MaxBodySizeMiddleware, max_body_size=200 * 1024 * 1024)
logger.info(f"Max upload size set to 200MB")

# ========== 미들웨어 설정 (등록 역순으로 실행됨 - 나중에 추가된 것이 먼저 실행) ==========

# 0. Metrics 미들웨어 (가장 나중에 실행 - 모든 요청 측정)
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
if METRICS_ENABLED:
    try:
        from app.middleware.metrics import MetricsMiddleware

        app.add_middleware(MetricsMiddleware)
        logger.info("Metrics middleware enabled")
    except Exception as e:
        logger.warning(f"Failed to enable Metrics middleware: {e}")

# 2. Security Headers 미들웨어
SECURITY_HEADERS_ENABLED = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
if SECURITY_HEADERS_ENABLED:
    try:
        from app.middleware.security_headers import SecurityHeadersMiddleware

        app.add_middleware(SecurityHeadersMiddleware)
        logger.info("Security Headers middleware enabled")
    except Exception as e:
        logger.warning(f"Failed to enable Security Headers middleware: {e}")

# 3. Rate Limiting 미들웨어
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
if RATE_LIMIT_ENABLED:
    try:
        from app.middleware.rate_limit import RateLimitMiddleware

        app.add_middleware(RateLimitMiddleware)
        logger.info("Rate Limiting middleware enabled")
    except Exception as e:
        logger.warning(f"Failed to enable Rate Limiting middleware: {e}")

# 4. PII 마스킹 미들웨어
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

# 5. Audit Log 미들웨어
AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
if AUDIT_LOG_ENABLED:
    try:
        from app.middleware.audit import AuditMiddleware

        app.add_middleware(AuditMiddleware)
        logger.info("Audit Log middleware enabled")
    except Exception as e:
        logger.warning(f"Failed to enable Audit Log middleware: {e}")
else:
    logger.info("Audit Log middleware disabled")

# 6. CORS 미들웨어 (가장 마지막에 추가 → 가장 먼저 실행됨)
# FastAPI 미들웨어는 역순으로 실행되므로, CORS를 마지막에 추가해야
# 다른 미들웨어의 에러 응답에도 CORS 헤더가 포함됨
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS middleware enabled for origins: {settings.cors_origins_list}")

# Prometheus 메트릭 엔드포인트
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ========== 전역 예외 핸들러 ==========


def add_cors_headers(response: JSONResponse, request: Request) -> JSONResponse:
    """
    예외 응답에 CORS 헤더를 추가합니다.

    CORSMiddleware가 예외 핸들러의 응답에 CORS 헤더를 추가하지 못하는 경우가 있어,
    모든 에러 응답에도 CORS 헤더가 포함되도록 수동으로 추가합니다.

    이를 통해 500 에러가 브라우저에서 CORS 에러로 표시되는 문제를 방지합니다.
    """
    origin = request.headers.get("origin", "")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 예외 핸들러 - 사용자 친화적 메시지로 변환"""
    # Accept-Language 헤더에서 언어 추출
    lang = request.headers.get("Accept-Language", "ko")
    lang = "ko" if "ko" in lang else "en"

    # HTTPException의 detail이 이미 dict인 경우 그대로 반환
    if isinstance(exc.detail, dict):
        response = JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
        return add_cors_headers(response, request)

    # 에러 분류 및 포맷팅
    user_error = classify_error(exc)
    error_response = format_error_response(user_error, lang=lang)

    response = JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )
    return add_cors_headers(response, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 유효성 검사 에러 핸들러"""
    lang = request.headers.get("Accept-Language", "ko")
    lang = "ko" if "ko" in lang else "en"

    # 에러 상세 정보 추출
    errors = exc.errors()
    error_details = []
    for error in errors:
        loc = " -> ".join(str(l) for l in error["loc"])
        error_details.append(f"{loc}: {error['msg']}")

    if lang == "ko":
        message = "입력 데이터가 올바르지 않습니다."
        suggestion = "요청 데이터를 확인해 주세요."
    else:
        message = "Invalid input data."
        suggestion = "Please check your request data."

    response = JSONResponse(
        status_code=422,
        content={
            "error": True,
            "category": ErrorCategory.VALIDATION,
            "message": message,
            "suggestion": suggestion,
            "details": error_details,
            "retryable": False,
        },
    )
    return add_cors_headers(response, request)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 핸들러 - 예상치 못한 에러 처리"""
    lang = request.headers.get("Accept-Language", "ko")
    lang = "ko" if "ko" in lang else "en"

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    user_error = classify_error(exc)
    error_response = format_error_response(user_error, lang=lang)

    response = JSONResponse(
        status_code=user_error.http_status,
        content=error_response,
    )
    return add_cors_headers(response, request)


@app.get("/")
async def root():
    """루트 엔드포인트 - frontend_dist가 있으면 index.html 반환"""
    frontend_dir = Path(__file__).parent.parent / "frontend_dist"
    if frontend_dir.exists():
        return FileResponse(frontend_dir / "index.html")
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "ok",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    from app.services.cache_service import CacheService

    db_status = "ok" if check_db_connection() else "error"
    redis_status = "ok" if CacheService.is_available() else "unavailable"

    overall = "healthy"
    if db_status != "ok":
        overall = "unhealthy"
    elif redis_status != "ok":
        overall = "degraded"

    return {
        "status": overall,
        "checks": {
            "database": db_status,
            "redis": redis_status,
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

# Notifications 라우터
try:
    from app.routers import notifications
    app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
    logger.info("Notifications router registered")
except Exception as e:
    logger.error(f"Failed to register notifications router: {e}")

# Feedback 라우터
try:
    from app.routers import feedback
    app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["feedback"])
    logger.info("Feedback router registered")
except Exception as e:
    logger.error(f"Failed to register feedback router: {e}")

# Proposals 라우터 (제안된 규칙)
try:
    from app.routers import proposals
    app.include_router(proposals.router, prefix="/api/v1/proposals", tags=["proposals"])
    logger.info("Proposals router registered")
except Exception as e:
    logger.error(f"Failed to register proposals router: {e}")

# Experiments 라우터 (A/B 테스트)
try:
    from app.routers import experiments
    app.include_router(experiments.router, prefix="/api/v1/experiments", tags=["experiments"])
    logger.info("Experiments router registered")
except Exception as e:
    logger.error(f"Failed to register experiments router: {e}")

# Alerts 라우터 (Prometheus AlertManager Webhook)
try:
    from app.routers import alerts
    app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["alerts"])
    logger.info("Alerts router registered")
except Exception as e:
    logger.error(f"Failed to register alerts router: {e}")

# Audit 라우터 (감사 로그)
try:
    from app.routers import audit
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    logger.info("Audit router registered")
except Exception as e:
    logger.error(f"Failed to register audit router: {e}")

# Scheduler 라우터 (스케줄러 관리)
try:
    from app.routers import scheduler
    app.include_router(scheduler.router, prefix="/api/v1/scheduler", tags=["scheduler"])
    logger.info("Scheduler router registered")

    # 기본 스케줄 작업 등록
    from app.services.scheduler_service import setup_default_jobs
    setup_default_jobs()
    logger.info("Default scheduler jobs registered")
except Exception as e:
    logger.error(f"Failed to register scheduler router: {e}")

# ERP/MES 라우터 (Mock API)
try:
    from app.routers import erp_mes
    app.include_router(erp_mes.router, prefix="/api/v1/erp-mes", tags=["erp-mes"])
    logger.info("ERP/MES router registered")
except Exception as e:
    logger.error(f"Failed to register erp-mes router: {e}")

# API Key 라우터
try:
    from app.routers import api_keys
    app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["api-keys"])
    logger.info("API Keys router registered")
except Exception as e:
    logger.error(f"Failed to register api-keys router: {e}")

# RAG 라우터 (문서/지식베이스)
try:
    from app.routers import rag
    app.include_router(rag.router, prefix="/api/v1", tags=["rag"])
    logger.info("RAG router registered")
except Exception as e:
    logger.error(f"Failed to register rag router: {e}")

# Settings 라우터 (시스템 설정)
try:
    from app.routers import settings as settings_router
    app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
    logger.info("Settings router registered")
except Exception as e:
    logger.error(f"Failed to register settings router: {e}")

# BI 라우터 (비즈니스 인텔리전스)
try:
    from app.routers import bi
    app.include_router(bi.router, prefix="/api/v1/bi", tags=["bi"])
    logger.info("BI router registered")
except Exception as e:
    logger.error(f"Failed to register bi router: {e}")

# MCP ToolHub 라우터 (외부 MCP 서버 연동)
try:
    from app.routers import mcp
    app.include_router(mcp.router, prefix="/api/v1", tags=["mcp"])
    logger.info("MCP ToolHub router registered")
except Exception as e:
    logger.error(f"Failed to register mcp router: {e}")

# Tenant Config 라우터 (Multi-Tenant Module Configuration)
try:
    from app.routers import tenant_config
    app.include_router(tenant_config.router, prefix="/api/v1/tenant-config", tags=["tenant-config"])
    logger.info("Tenant Config router registered")
except Exception as e:
    logger.error(f"Failed to register tenant-config router: {e}")

# Prompts 라우터 (Prompt Template 관리)
try:
    from app.routers import prompts
    app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
    logger.info("Prompts router registered")
except Exception as e:
    logger.error(f"Failed to register prompts router: {e}")

# ========== 플러그인 모듈 로딩 ==========
# modules/ 디렉토리의 매니페스트 기반 동적 라우터 로딩
try:
    from app.module_loader import load_module_routers, sync_modules_to_db

    module_result = load_module_routers(app)
    logger.info(
        f"Plugin modules loaded: {len(module_result['loaded'])} success, "
        f"{len(module_result['failed'])} failed"
    )

    # 개발 환경에서만 모듈 → DB 동기화 (프로덕션은 마이그레이션 사용)
    if settings.environment == "development":
        try:
            sync_modules_to_db()
        except Exception as sync_error:
            logger.warning(f"Module DB sync skipped: {sync_error}")
except Exception as e:
    logger.warning(f"Plugin module loading skipped: {e}")

# ============================================
# V2.0 API Endpoints
# ============================================

# V2.0 Trust 라우터 (Progressive Trust Model)
try:
    from app.routers import trust
    app.include_router(trust.router, prefix="/api/v2/trust", tags=["v2-trust"])
    logger.info("V2 Trust router registered")
except Exception as e:
    logger.error(f"Failed to register v2 trust router: {e}")

# V2.0 Feature Flags 라우터
try:
    from app.routers import feature_flags
    app.include_router(feature_flags.router, prefix="/api/v2/feature-flags", tags=["v2-feature-flags"])
    logger.info("V2 Feature Flags router registered")
except Exception as e:
    logger.error(f"Failed to register v2 feature-flags router: {e}")

# Deployments 라우터 (Canary Deployment)
try:
    from app.routers import deployments
    app.include_router(deployments.router, prefix="/api/v1", tags=["deployments"])
    logger.info("Deployments router registered")
except Exception as e:
    logger.error(f"Failed to register deployments router: {e}")

# Samples 라우터 (Sample Curation)
try:
    from app.routers import samples
    app.include_router(samples.router, prefix="/api/v1", tags=["samples"])
    app.include_router(samples.golden_router, prefix="/api/v1", tags=["golden-sets"])
    logger.info("Samples router registered")
except Exception as e:
    logger.error(f"Failed to register samples router: {e}")

# Rule Extraction 라우터 (Decision Tree 기반 규칙 추출)
try:
    from app.routers import rule_extraction
    logger.info(f"rule_extraction module imported, router: {rule_extraction.router}, routes: {len(rule_extraction.router.routes)}")
    app.include_router(rule_extraction.router, prefix="/api/v1", tags=["rule-extraction"])
    logger.info("Rule extraction router registered successfully")
    # Verify routes were added
    rule_routes = [r for r in app.routes if '/rule-extraction' in str(getattr(r, 'path', ''))]
    logger.info(f"Verified {len(rule_routes)} rule-extraction routes in app")
except Exception as e:
    logger.error(f"Failed to register rule extraction router: {e}", exc_info=True)

# Users 라우터 (RBAC 및 Data Scope 관리)
try:
    from app.routers import users
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    logger.info("Users router registered")
except Exception as e:
    logger.error(f"Failed to register users router: {e}")

# Module Management 라우터 (모듈 업로드/제거)
try:
    from app.routers import modules
    app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])
    logger.info("Module management router registered")
except Exception as e:
    logger.error(f"Failed to register module management router: {e}")


# ========== 프론트엔드 정적 파일 서빙 (SPA) ==========
# frontend/dist 폴더가 있으면 정적 파일 서빙
FRONTEND_DIR = Path(__file__).parent.parent / "frontend_dist"
if FRONTEND_DIR.exists():
    # 정적 에셋 (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

    # SPA 라우팅 - 모든 프론트엔드 경로에 대해 index.html 반환
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 라우팅 - API가 아닌 모든 경로에 대해 index.html 반환"""
        # API, docs, health 등은 이미 위에서 처리됨
        # 정적 파일이 있으면 반환
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # 그 외 모든 경로는 index.html로 (SPA 라우팅)
        return FileResponse(FRONTEND_DIR / "index.html")

    logger.info(f"Frontend static files served from {FRONTEND_DIR}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
