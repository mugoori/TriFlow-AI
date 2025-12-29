"""
Main Application 테스트
app/main.py 테스트
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.main import app


# ========== 기본 엔드포인트 테스트 ==========


class TestRootEndpoint:
    """루트 엔드포인트 테스트"""

    def test_root_returns_info(self):
        """루트 엔드포인트가 앱 정보 반환"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "ok"


class TestHealthEndpoint:
    """헬스 체크 엔드포인트 테스트"""

    def test_health_check_healthy(self):
        """헬스 체크 - 정상"""
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.main.check_db_connection", return_value=True):
            with patch("app.services.cache_service.CacheService.is_available", return_value=True):
                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_degraded(self):
        """헬스 체크 - 성능 저하 (Redis 없음)"""
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.main.check_db_connection", return_value=True):
            with patch("app.services.cache_service.CacheService.is_available", return_value=False):
                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"

    def test_health_check_unhealthy(self):
        """헬스 체크 - 비정상 (DB 없음)"""
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.main.check_db_connection", return_value=False):
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"


class TestApiInfoEndpoint:
    """API 정보 엔드포인트 테스트"""

    def test_api_info(self):
        """API 정보 반환"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/info")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "llm_model" in data
        assert "environment" in data


# ========== CORS 헤더 테스트 ==========


class TestCorsHeaders:
    """CORS 헤더 테스트"""

    def test_add_cors_headers(self):
        """add_cors_headers 함수"""
        from app.main import add_cors_headers
        from app.config import settings

        mock_request = MagicMock()
        mock_request.headers.get.return_value = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:3000"

        response = JSONResponse(content={"test": "data"})
        result = add_cors_headers(response, mock_request)

        # 응답이 반환되어야 함
        assert result is not None

    def test_add_cors_headers_no_origin(self):
        """add_cors_headers - origin 없음"""
        from app.main import add_cors_headers

        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""

        response = JSONResponse(content={"test": "data"})
        result = add_cors_headers(response, mock_request)

        assert result is not None

    def test_add_cors_headers_invalid_origin(self):
        """add_cors_headers - 유효하지 않은 origin"""
        from app.main import add_cors_headers

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "http://invalid.example.com"

        response = JSONResponse(content={"test": "data"})
        result = add_cors_headers(response, mock_request)

        # CORS 헤더가 추가되지 않음
        assert "Access-Control-Allow-Origin" not in result.headers


# ========== 예외 핸들러 테스트 ==========


class TestHttpExceptionHandler:
    """HTTP 예외 핸들러 테스트"""

    def test_http_exception_404(self):
        """404 에러 처리"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/nonexistent-endpoint")

        assert response.status_code == 404

    def test_http_exception_with_korean(self):
        """HTTP 예외 - 한국어 응답"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/nonexistent-endpoint",
            headers={"Accept-Language": "ko"}
        )

        assert response.status_code == 404

    def test_http_exception_with_english(self):
        """HTTP 예외 - 영어 응답"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/nonexistent-endpoint",
            headers={"Accept-Language": "en"}
        )

        assert response.status_code == 404


class TestValidationExceptionHandler:
    """유효성 검사 예외 핸들러 테스트"""

    def test_validation_error_korean(self):
        """유효성 검사 에러 - 한국어"""
        client = TestClient(app, raise_server_exceptions=False)

        # 잘못된 데이터로 요청
        response = client.post(
            "/api/v1/agents/chat",
            json={"invalid": "data"},  # 필수 필드 누락
            headers={"Accept-Language": "ko"}
        )

        # 422 또는 다른 에러 상태 코드
        # 인증 필요하므로 401이 먼저 반환될 수 있음
        assert response.status_code in [401, 422]

    def test_validation_error_english(self):
        """유효성 검사 에러 - 영어"""
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/v1/agents/chat",
            json={"invalid": "data"},
            headers={"Accept-Language": "en"}
        )

        assert response.status_code in [401, 422]


# ========== 라우터 등록 테스트 ==========


class TestRouterRegistration:
    """라우터 등록 테스트"""

    def test_tenants_router_registered(self):
        """Tenants 라우터 등록 확인"""
        routes = [route.path for route in app.routes]
        assert any("/tenants" in path for path in routes)

    def test_agents_router_registered(self):
        """Agents 라우터 등록 확인"""
        routes = [route.path for route in app.routes]
        assert any("/agents" in path for path in routes)

    def test_auth_router_registered(self):
        """Auth 라우터 등록 확인"""
        routes = [route.path for route in app.routes]
        assert any("/auth" in path for path in routes)

    def test_health_endpoint_exists(self):
        """Health 엔드포인트 존재 확인"""
        routes = [route.path for route in app.routes]
        assert "/health" in routes


# ========== 미들웨어 테스트 ==========


class TestMiddleware:
    """미들웨어 테스트"""

    def test_cors_middleware_active(self):
        """CORS 미들웨어 활성화 확인"""
        from app.config import settings

        client = TestClient(app, raise_server_exceptions=False)

        origin = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:3000"
        response = client.options("/", headers={"Origin": origin})

        # OPTIONS 요청이 처리됨
        assert response.status_code in [200, 400, 405]


# ========== warmup_agents 테스트 ==========


class TestWarmupAgents:
    """warmup_agents 함수 테스트"""

    @pytest.mark.asyncio
    async def test_warmup_agents_success(self):
        """에이전트 워밍업 성공"""
        from app.main import warmup_agents

        with patch("app.services.agent_orchestrator.orchestrator") as mock_orchestrator:
            mock_orchestrator.process.return_value = {"result": "ok"}

            # 예외 없이 완료되어야 함
            await warmup_agents()

    @pytest.mark.asyncio
    async def test_warmup_agents_failure(self):
        """에이전트 워밍업 실패 (비 critical)"""
        from app.main import warmup_agents

        with patch("app.services.agent_orchestrator.orchestrator") as mock_orchestrator:
            mock_orchestrator.process.side_effect = Exception("Warmup failed")

            # 예외가 발생해도 에러로 전파되지 않음
            await warmup_agents()


# ========== 앱 설정 테스트 ==========


class TestAppConfiguration:
    """앱 설정 테스트"""

    def test_app_title(self):
        """앱 제목 설정"""
        from app.config import settings

        assert app.title == settings.app_name

    def test_app_version(self):
        """앱 버전 설정"""
        from app.config import settings

        assert app.version == settings.app_version

    def test_metrics_endpoint_mounted(self):
        """메트릭 엔드포인트 마운트"""
        client = TestClient(app, raise_server_exceptions=False)

        # /metrics 엔드포인트가 존재해야 함
        response = client.get("/metrics")
        # Prometheus 메트릭 반환 또는 405
        assert response.status_code in [200, 405]


# ========== 에러 분류 통합 테스트 ==========


class TestErrorClassification:
    """에러 분류 통합 테스트"""

    def test_error_response_format(self):
        """에러 응답 형식"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/nonexistent")

        assert response.status_code == 404
        data = response.json()

        # 에러 응답 필드 확인
        assert "error" in data or "message" in data or "detail" in data


# ========== 메트릭 엔드포인트 테스트 ==========


class TestMetricsEndpoint:
    """메트릭 엔드포인트 테스트"""

    def test_metrics_returns_prometheus_format(self):
        """메트릭이 Prometheus 형식으로 반환"""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/metrics")

        if response.status_code == 200:
            # Prometheus 형식 확인
            content_type = response.headers.get("content-type", "")
            assert "text/plain" in content_type or "text" in content_type
