"""
Rate Limiting 미들웨어 테스트
app/middleware/rate_limit.py의 RateLimitMiddleware 테스트
"""
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient
from fastapi import FastAPI


# ========== RATE_LIMIT_RULES 상수 테스트 ==========


class TestRateLimitRules:
    """Rate Limit 규칙 상수 테스트"""

    def test_rate_limit_rules_exist(self):
        """Rate Limit 규칙 존재"""
        from app.middleware.rate_limit import RATE_LIMIT_RULES

        assert "/api/v1/auth/login" in RATE_LIMIT_RULES
        assert "/api/v1/agents/chat" in RATE_LIMIT_RULES

    def test_rate_limit_rules_format(self):
        """Rate Limit 규칙 형식 (max_requests, window_seconds)"""
        from app.middleware.rate_limit import RATE_LIMIT_RULES

        for path, (max_req, window) in RATE_LIMIT_RULES.items():
            assert isinstance(max_req, int)
            assert isinstance(window, int)
            assert max_req > 0
            assert window > 0

    def test_default_rate_limit(self):
        """기본 Rate Limit"""
        from app.middleware.rate_limit import DEFAULT_RATE_LIMIT

        assert DEFAULT_RATE_LIMIT == (200, 60)

    def test_excluded_paths(self):
        """제외 경로"""
        from app.middleware.rate_limit import EXCLUDED_PATHS

        assert "/health" in EXCLUDED_PATHS
        assert "/docs" in EXCLUDED_PATHS


# ========== RateLimitMiddleware 초기화 테스트 ==========


class TestRateLimitMiddlewareInit:
    """RateLimitMiddleware 초기화 테스트"""

    def test_middleware_instantiation(self):
        """미들웨어 인스턴스화"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        assert middleware.app == app


# ========== _get_client_ip 테스트 ==========


class TestGetClientIP:
    """_get_client_ip 메서드 테스트"""

    def test_get_ip_from_forwarded_for(self):
        """X-Forwarded-For 헤더에서 IP 추출"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        mock_request = MagicMock()
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.100, 10.0.0.1, 172.16.0.1"
        }

        result = middleware._get_client_ip(mock_request)

        assert result == "192.168.1.100"

    def test_get_ip_from_real_ip(self):
        """X-Real-IP 헤더에서 IP 추출"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        mock_request = MagicMock()
        mock_headers = MagicMock()
        mock_headers.get = lambda k, d=None: {"X-Real-IP": "192.168.1.200"}.get(k, d)
        mock_headers.__contains__ = lambda self, k: k in ["X-Real-IP"]
        mock_request.headers = mock_headers

        result = middleware._get_client_ip(mock_request)

        assert result == "192.168.1.200"

    def test_get_ip_from_client(self):
        """직접 연결에서 IP 추출"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        mock_request = MagicMock()
        mock_headers = MagicMock()
        mock_headers.get = lambda k, d=None: None
        mock_headers.__contains__ = lambda self, k: False
        mock_request.headers = mock_headers
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        result = middleware._get_client_ip(mock_request)

        assert result == "127.0.0.1"

    def test_get_ip_unknown(self):
        """IP를 알 수 없는 경우"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        mock_request = MagicMock()
        mock_headers = MagicMock()
        mock_headers.get = lambda k, d=None: None
        mock_headers.__contains__ = lambda self, k: False
        mock_request.headers = mock_headers
        mock_request.client = None

        result = middleware._get_client_ip(mock_request)

        assert result == "unknown"


# ========== _get_rate_limit 테스트 ==========


class TestGetRateLimit:
    """_get_rate_limit 메서드 테스트"""

    def test_exact_path_match(self):
        """정확한 경로 매칭"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        result = middleware._get_rate_limit("/api/v1/auth/login")

        assert result == (10, 60)

    def test_prefix_path_match(self):
        """접두사 경로 매칭"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        # /api/v1/agents/chat/stream → /api/v1/agents/chat
        result = middleware._get_rate_limit("/api/v1/agents/chat/stream")

        assert result == (30, 60)

    def test_default_rate_limit(self):
        """기본 Rate Limit 반환"""
        from app.middleware.rate_limit import RateLimitMiddleware, DEFAULT_RATE_LIMIT

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        result = middleware._get_rate_limit("/api/v1/unknown/path")

        assert result == DEFAULT_RATE_LIMIT


# ========== _check_rate_limit 테스트 ==========


class TestCheckRateLimit:
    """_check_rate_limit 메서드 테스트"""

    @patch("app.middleware.rate_limit.CacheService")
    def test_check_rate_limit_allowed(self, mock_cache):
        """Rate Limit 허용"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = True
        mock_cache.get.return_value = "5"

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        allowed, remaining, reset_time = middleware._check_rate_limit(
            "rate_limit:127.0.0.1:/test", 10, 60
        )

        assert allowed is True
        assert remaining == 5

    @patch("app.middleware.rate_limit.CacheService")
    def test_check_rate_limit_denied(self, mock_cache):
        """Rate Limit 거부"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = False

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        allowed, remaining, reset_time = middleware._check_rate_limit(
            "rate_limit:127.0.0.1:/test", 10, 60
        )

        assert allowed is False
        assert remaining == 0

    @patch("app.middleware.rate_limit.CacheService")
    def test_check_rate_limit_no_cache_value(self, mock_cache):
        """캐시 값 없음"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = True
        mock_cache.get.return_value = None

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        allowed, remaining, reset_time = middleware._check_rate_limit(
            "rate_limit:127.0.0.1:/test", 10, 60
        )

        assert allowed is True
        assert remaining == 9

    @patch("app.middleware.rate_limit.CacheService")
    def test_check_rate_limit_invalid_cache_value(self, mock_cache):
        """유효하지 않은 캐시 값"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = True
        mock_cache.get.return_value = "invalid"

        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        allowed, remaining, reset_time = middleware._check_rate_limit(
            "rate_limit:127.0.0.1:/test", 10, 60
        )

        assert allowed is True
        assert remaining == 9


# ========== dispatch 테스트 ==========


class TestDispatch:
    """dispatch 메서드 테스트"""

    @patch("app.middleware.rate_limit.CacheService")
    def test_dispatch_options_request(self, mock_cache):
        """OPTIONS 요청 (CORS preflight) - Rate Limit 제외"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.options("/api/v1/test")

        # OPTIONS 요청은 Rate Limit 체크하지 않음
        assert response.status_code in [200, 405]  # 405도 가능

    @patch("app.middleware.rate_limit.CacheService")
    def test_dispatch_excluded_path(self, mock_cache):
        """제외 경로 - Rate Limit 제외"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        # Rate Limit 헤더 없음
        assert "X-RateLimit-Limit" not in response.headers

    @patch("app.middleware.rate_limit.CacheService")
    def test_dispatch_allowed(self, mock_cache):
        """Rate Limit 허용"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = True
        mock_cache.get.return_value = "1"

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @patch("app.middleware.rate_limit.CacheService")
    def test_dispatch_rate_limited(self, mock_cache):
        """Rate Limit 거부 - 429 응답"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = False

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert response.status_code == 429
        assert response.json()["category"] == "rate_limit"
        assert "retry_after" in response.json()

    @patch("app.middleware.rate_limit.CacheService")
    def test_dispatch_rate_limited_with_cors(self, mock_cache):
        """Rate Limit 거부 + CORS 헤더"""
        from app.middleware.rate_limit import RateLimitMiddleware, settings

        mock_cache.rate_limit.return_value = False

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        # settings.cors_origins_list에 포함된 origin으로 요청
        origin = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:3000"
        response = client.get("/api/v1/test", headers={"origin": origin})

        assert response.status_code == 429


# ========== 통합 테스트 ==========


class TestIntegration:
    """통합 테스트"""

    @patch("app.middleware.rate_limit.CacheService")
    def test_auth_login_rate_limit(self, mock_cache):
        """인증 엔드포인트 Rate Limit"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = True
        mock_cache.get.return_value = "5"

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.post("/api/v1/auth/login")
        async def login():
            return {"token": "abc"}

        client = TestClient(app)
        response = client.post("/api/v1/auth/login")

        assert response.status_code == 200
        # 인증 엔드포인트 제한: 10 req/min
        assert response.headers["X-RateLimit-Limit"] == "10"

    @patch("app.middleware.rate_limit.CacheService")
    def test_agents_chat_rate_limit(self, mock_cache):
        """에이전트 채팅 Rate Limit"""
        from app.middleware.rate_limit import RateLimitMiddleware

        mock_cache.rate_limit.return_value = True
        mock_cache.get.return_value = "10"

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        @app.post("/api/v1/agents/chat")
        async def chat():
            return {"response": "Hello"}

        client = TestClient(app)
        response = client.post("/api/v1/agents/chat")

        assert response.status_code == 200
        # 에이전트 채팅 제한: 30 req/min
        assert response.headers["X-RateLimit-Limit"] == "30"

    @patch("app.middleware.rate_limit.CacheService")
    def test_docs_excluded(self, mock_cache):
        """/docs 경로 제외"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        client = TestClient(app)
        response = client.get("/docs")

        # /docs는 제외되어 Rate Limit 헤더 없음
        assert "X-RateLimit-Limit" not in response.headers

    @patch("app.middleware.rate_limit.CacheService")
    def test_redoc_excluded(self, mock_cache):
        """/redoc 경로 제외"""
        from app.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        app.add_middleware(RateLimitMiddleware)

        client = TestClient(app)
        response = client.get("/redoc")

        # /redoc는 제외되어 Rate Limit 헤더 없음
        assert "X-RateLimit-Limit" not in response.headers
