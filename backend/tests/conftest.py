"""
TriFlow AI - Test Configuration
================================
pytest fixtures and configuration for backend tests
Uses SQLite for testing by default, PostgreSQL if available

Mock Mode:
- By default, tests use Mock Agents (no Anthropic API calls)
- Set TRIFLOW_USE_REAL_API=1 to use real API for integration testing
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load .env file first to get real API keys
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Check if we should use real API (for integration tests)
USE_REAL_API = os.environ.get("TRIFLOW_USE_REAL_API", "0") == "1"

# Check if PostgreSQL is available
def check_postgres_available():
    """Check if PostgreSQL is accessible."""
    try:
        pg_engine = create_engine(
            "postgresql://triflow:triflow_dev_password@localhost:5432/postgres",
            connect_args={"connect_timeout": 2}
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        pg_engine.dispose()
        return True
    except Exception:
        return False

USE_SQLITE = os.environ.get("USE_SQLITE", "1") == "1" or not check_postgres_available()

# Auto-skip DB-dependent tests when using SQLite
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "requires_db: mark test as requiring PostgreSQL database")


def pytest_collection_modifyitems(config, items):
    """Skip tests that require PostgreSQL when using SQLite."""
    if not USE_SQLITE:
        return

    skip_db = pytest.mark.skip(reason="Test requires PostgreSQL database (using SQLite)")
    for item in items:
        # Skip tests marked with requires_db
        if "requires_db" in item.keywords:
            item.add_marker(skip_db)
        # Skip tests that use db_session, client, authenticated_client, admin_client fixtures
        # (These require PostgreSQL with UUID support)
        if hasattr(item, 'fixturenames'):
            db_fixtures = {'db_session', 'client', 'authenticated_client', 'admin_client'}
            if db_fixtures & set(item.fixturenames):
                item.add_marker(skip_db)


# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"

if USE_SQLITE:
    # Use SQLite for testing (no external dependencies)
    TEST_DATABASE_URL = "sqlite:///./test_triflow.db"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    # Use PostgreSQL test database
    TEST_DATABASE_URL = "postgresql://triflow:triflow_dev_password@localhost:5432/triflow_ai_test"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

os.environ["REDIS_URL"] = "redis://:triflow_redis_password@localhost:6379/15"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
# ANTHROPIC_API_KEY is loaded from .env file (real key for integration tests)
# Disable audit and PII middleware for tests (causes body reading conflicts)
os.environ["AUDIT_LOG_ENABLED"] = "false"
os.environ["PII_MASKING_ENABLED"] = "false"
# Disable rate limiting for tests (prevents test failures due to rapid API calls)
os.environ["RATE_LIMIT_ENABLED"] = "false"

# Now import app modules
from app.main import app
from app.database import get_db, Base


# Test database setup
if USE_SQLITE:
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    # Enable foreign key support for SQLite
    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    test_engine = create_engine(
        TEST_DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def create_test_database():
    """Create test database if it doesn't exist."""
    if USE_SQLITE:
        # SQLite creates file automatically
        return
    # Connect to default postgres database to create test database
    admin_engine = create_engine(
        "postgresql://triflow:triflow_dev_password@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as conn:
        # Check if test database exists
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'triflow_ai_test'")
        )
        if not result.fetchone():
            conn.execute(text("CREATE DATABASE triflow_ai_test"))
    admin_engine.dispose()


def create_schemas():
    """Create required schemas in test database."""
    if USE_SQLITE:
        # SQLite doesn't support schemas
        return
    with test_engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS bi"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS rag"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS audit"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS aas"))
        conn.commit()


def create_audit_tables():
    """Create audit tables used by raw SQL queries."""
    if USE_SQLITE:
        # SQLite version of audit table
        with test_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    user_id TEXT,
                    action VARCHAR(100) NOT NULL,
                    resource VARCHAR(100),
                    resource_type VARCHAR(100) NOT NULL,
                    resource_id VARCHAR(255),
                    method VARCHAR(10),
                    path VARCHAR(500),
                    status_code INTEGER,
                    ip_address VARCHAR(45),
                    user_agent VARCHAR(500),
                    request_body TEXT,
                    response_summary VARCHAR(500),
                    duration_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        return

    with test_engine.connect() as conn:
        # uuid-ossp extension for uuid_generate_v4()
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))

        # Audit logs table (simplified non-partitioned version for tests)
        # resource_type 컬럼 포함 (production DB와 동일)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit.audit_logs (
                log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                tenant_id UUID,
                user_id UUID,
                action VARCHAR(100) NOT NULL,
                resource VARCHAR(100),
                resource_type VARCHAR(100) NOT NULL,
                resource_id VARCHAR(255),
                method VARCHAR(10),
                path VARCHAR(500),
                status_code INTEGER,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                request_body JSONB,
                response_summary VARCHAR(500),
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database once per session."""
    create_test_database()
    create_schemas()
    create_audit_tables()
    yield
    # Clean up SQLite file after tests
    if USE_SQLITE:
        import os
        # Dispose engine to release file handles (Windows compatibility)
        test_engine.dispose()
        try:
            os.remove("./test_triflow.db")
        except (FileNotFoundError, PermissionError):
            pass  # Ignore if file doesn't exist or is locked


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """Create a fresh database session for each test."""
    # Create tables
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after each test for isolation
        Base.metadata.drop_all(bind=test_engine)


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Create an authenticated client with a test user."""
    # Register a test user
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@triflow.ai",
            "password": "TestPassword123!",
            "display_name": "Test User"
        }
    )

    if register_response.status_code == 200:
        # Response is LoginResponse: {user: ..., tokens: {access_token, ...}}
        tokens = register_response.json().get("tokens", {})
        token = tokens.get("access_token")
    else:
        # User might already exist, try login (JSON body with email)
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@triflow.ai",
                "password": "TestPassword123!"
            }
        )
        tokens = login_response.json().get("tokens", {})
        token = tokens.get("access_token")

    if token:
        client.headers["Authorization"] = f"Bearer {token}"

    return client


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """Create an authenticated client with admin privileges."""
    # For testing, we'll create an admin user
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@triflow.ai",
            "password": "AdminPassword123!",
            "display_name": "Admin User",
            "role": "admin"
        }
    )

    if register_response.status_code == 200:
        tokens = register_response.json().get("tokens", {})
        token = tokens.get("access_token")
    else:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@triflow.ai",
                "password": "AdminPassword123!"
            }
        )
        tokens = login_response.json().get("tokens", {})
        token = tokens.get("access_token")

    if token:
        client.headers["Authorization"] = f"Bearer {token}"

    return client


# Test data fixtures
@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for testing."""
    return {
        "sensor_id": "TEMP-001",
        "sensor_type": "temperature",
        "value": 75.5,
        "unit": "°C",
        "location": "Line 1",
        "metadata": {"zone": "production"}
    }


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing (matches WorkflowCreate schema)."""
    return {
        "name": "Temperature Alert Workflow",
        "description": "Alert when temperature exceeds threshold",
        "dsl_definition": {
            "name": "Temperature Alert Workflow",
            "description": "Alert when temperature exceeds threshold",
            "trigger": {
                "type": "event",
                "config": {
                    "sensor_type": "temperature",
                    "operator": ">=",
                    "threshold": 80
                }
            },
            "nodes": [
                {
                    "id": "node-1",
                    "type": "condition",
                    "config": {"condition": "temperature >= 80"},
                    "next": ["node-2"]
                },
                {
                    "id": "node-2",
                    "type": "action",
                    "config": {
                        "action": "send_slack_notification",
                        "channel": "#alerts",
                        "message": "Temperature exceeded threshold"
                    },
                    "next": []
                }
            ]
        }
    }


@pytest.fixture
def sample_ruleset_data():
    """Sample Rhai ruleset for testing (matches RulesetCreate schema)."""
    return {
        "name": "Temperature Check Rule",
        "description": "Check temperature thresholds",
        "rhai_script": """// Temperature safety check
fn check_temperature(temp) {
    if temp >= 80 {
        return "critical";
    } else if temp >= 60 {
        return "warning";
    }
    return "normal";
}

let result = check_temperature(sensor_value);
result"""
    }


# ============ Mock Agent Fixtures ============
# These fixtures provide mock responses for AI agent tests
# to avoid hitting the Anthropic API during CI/CD

class MockAgentResponse:
    """Mock response data for agent tests."""

    @staticmethod
    def meta_router_general():
        """Mock response for general queries."""
        return {
            "response": "안녕하세요! TriFlow AI입니다. 센서 데이터 분석, 워크플로우 생성, 통계 조회 등을 도와드릴 수 있습니다.",
            "tool_calls": [
                {
                    "tool": "classify_intent",
                    "input": {"intent": "general", "confidence": 0.95, "reason": "일반적인 인사말"},
                    "result": {"success": True, "intent": "general", "confidence": 0.95, "reason": "일반적인 인사말"},
                },
                {
                    "tool": "route_request",
                    "input": {"target_agent": "general", "processed_request": "안녕하세요"},
                    "result": {"success": True, "target_agent": "general", "processed_request": "안녕하세요", "context": {}},
                },
            ],
            "iterations": 1,
        }

    @staticmethod
    def meta_router_judgment():
        """Mock response for judgment/sensor queries."""
        return {
            "response": "",
            "tool_calls": [
                {
                    "tool": "classify_intent",
                    "input": {"intent": "judgment", "confidence": 0.92, "reason": "센서 데이터 분석 요청"},
                    "result": {"success": True, "intent": "judgment", "confidence": 0.92, "reason": "센서 데이터 분석 요청"},
                },
                {
                    "tool": "extract_slots",
                    "input": {"slots": {"sensor_type": "temperature"}},
                    "result": {"success": True, "slots": {"sensor_type": "temperature"}},
                },
                {
                    "tool": "route_request",
                    "input": {"target_agent": "judgment", "processed_request": "온도 센서 데이터를 분석해주세요"},
                    "result": {"success": True, "target_agent": "judgment", "processed_request": "온도 센서 데이터를 분석해주세요", "context": {}},
                },
            ],
            "iterations": 1,
        }

    @staticmethod
    def meta_router_workflow():
        """Mock response for workflow queries."""
        return {
            "response": "",
            "tool_calls": [
                {
                    "tool": "classify_intent",
                    "input": {"intent": "workflow", "confidence": 0.88, "reason": "워크플로우 생성 요청"},
                    "result": {"success": True, "intent": "workflow", "confidence": 0.88, "reason": "워크플로우 생성 요청"},
                },
                {
                    "tool": "route_request",
                    "input": {"target_agent": "workflow", "processed_request": "온도가 80도 이상일 때 알림을 보내는 워크플로우를 만들어줘"},
                    "result": {"success": True, "target_agent": "workflow", "processed_request": "온도가 80도 이상일 때 알림을 보내는 워크플로우를 만들어줘", "context": {}},
                },
            ],
            "iterations": 1,
        }

    @staticmethod
    def meta_router_bi():
        """Mock response for BI/statistics queries."""
        return {
            "response": "",
            "tool_calls": [
                {
                    "tool": "classify_intent",
                    "input": {"intent": "bi", "confidence": 0.90, "reason": "통계 데이터 조회 요청"},
                    "result": {"success": True, "intent": "bi", "confidence": 0.90, "reason": "통계 데이터 조회 요청"},
                },
                {
                    "tool": "route_request",
                    "input": {"target_agent": "bi", "processed_request": "지난 주 생산량 통계를 보여줘"},
                    "result": {"success": True, "target_agent": "bi", "processed_request": "지난 주 생산량 통계를 보여줘", "context": {}},
                },
            ],
            "iterations": 1,
        }

    @staticmethod
    def judgment_agent():
        """Mock response for Judgment Agent."""
        return {
            "response": "현재 온도 센서 데이터를 분석했습니다. 모든 센서가 정상 범위 내에 있습니다. 평균 온도: 72.5°C, 최고: 78°C, 최저: 65°C",
            "tool_calls": [
                {
                    "tool": "get_sensor_data",
                    "input": {"sensor_type": "temperature", "limit": 10},
                    "result": {"success": True, "sensors": [{"id": "TEMP-001", "value": 72.5}]},
                },
                {
                    "tool": "analyze_sensors",
                    "input": {"sensors": ["TEMP-001"], "analysis_type": "statistics"},
                    "result": {"success": True, "analysis": {"avg": 72.5, "max": 78, "min": 65}},
                },
            ],
            "iterations": 2,
        }

    @staticmethod
    def workflow_agent():
        """Mock response for Workflow Planner Agent."""
        return {
            "response": "온도 알림 워크플로우를 생성했습니다. 온도가 80°C 이상이 되면 Slack #alerts 채널로 알림이 전송됩니다.",
            "tool_calls": [
                {
                    "tool": "create_workflow",
                    "input": {
                        "name": "Temperature Alert",
                        "trigger": {"type": "condition", "sensor": "temperature", "operator": ">=", "value": 80},
                        "actions": [{"type": "slack_notification", "channel": "#alerts"}],
                    },
                    "result": {"success": True, "workflow_id": "wf-test-001"},
                },
            ],
            "iterations": 1,
        }

    @staticmethod
    def bi_agent():
        """Mock response for BI Planner Agent."""
        return {
            "response": "지난 주 생산량 통계입니다:\n- 총 생산량: 15,230 units\n- 일평균: 2,175 units\n- 최고 생산일: 화요일 (2,890 units)",
            "tool_calls": [
                {
                    "tool": "execute_sql",
                    "input": {"query": "SELECT date, count(*) FROM production WHERE date >= DATE_SUB(NOW(), INTERVAL 7 DAY) GROUP BY date"},
                    "result": {"success": True, "data": [{"date": "2024-01-15", "count": 2890}]},
                },
            ],
            "iterations": 1,
        }

    @staticmethod
    def learning_agent():
        """Mock response for Learning Agent."""
        return {
            "response": "새로운 룰셋을 생성했습니다. 온도가 80°C 이상이면 '위험', 60°C 이상이면 '경고', 그 외에는 '정상'으로 판단합니다.",
            "tool_calls": [
                {
                    "tool": "create_ruleset",
                    "input": {"name": "Temperature Rule", "conditions": [{"threshold": 80, "level": "danger"}, {"threshold": 60, "level": "warning"}]},
                    "result": {"success": True, "ruleset_id": "rs-test-001"},
                },
            ],
            "iterations": 1,
        }


def create_mock_agent(response_func):
    """Create a mock agent that returns predetermined responses."""
    mock = MagicMock()
    mock.run.return_value = response_func()
    mock.parse_routing_result.return_value = {
        "target_agent": response_func().get("tool_calls", [{}])[-1].get("result", {}).get("target_agent", "general"),
        "processed_request": "",
        "context": {},
        "intent": None,
        "slots": {},
    }
    mock.name = "MockAgent"
    mock.model = "mock-model"
    return mock


def create_mock_orchestrator(response_data):
    """Create a mock orchestrator that returns predetermined responses."""
    mock = MagicMock()
    mock.process.return_value = response_data
    mock.get_agent_status.return_value = {
        "meta_router": {"name": "MetaRouterAgent", "model": "mock-model", "available": True},
        "judgment": {"name": "JudgmentAgent", "model": "mock-model", "available": True},
        "workflow": {"name": "WorkflowPlannerAgent", "model": "mock-model", "available": True},
        "bi": {"name": "BIPlannerAgent", "model": "mock-model", "available": True},
        "learning": {"name": "LearningAgent", "model": "mock-model", "available": True},
    }
    mock.execute_direct.return_value = response_data
    return mock


@pytest.fixture(scope="function")
def mock_agents(request):
    """
    Fixture to mock the orchestrator for chat tests.

    This fixture patches the orchestrator in the routers module
    so tests don't need actual Anthropic API calls.

    Usage:
        @pytest.mark.usefixtures("mock_agents")
        async def test_something(authenticated_client):
            ...

    To use real API (for integration tests):
        TRIFLOW_USE_REAL_API=1 pytest tests/test_chat.py
    """
    if USE_REAL_API:
        # Don't mock, use real agents
        yield
        return

    # Create mock orchestrator with general response
    mock_response = {
        "response": "안녕하세요! TriFlow AI입니다. 센서 데이터 분석, 워크플로우 생성, 통계 조회 등을 도와드릴 수 있습니다.",
        "agent_name": "MetaRouterAgent",
        "tool_calls": [],
        "iterations": 1,
        "routing_info": {"target_agent": "general", "intent": "general"},
    }
    mock_orchestrator = create_mock_orchestrator(mock_response)

    # Patch the orchestrator instance
    with patch("app.routers.agents.orchestrator", mock_orchestrator):
        yield


@pytest.fixture(scope="function")
def mock_meta_router_judgment():
    """Mock orchestrator to route to Judgment agent."""
    if USE_REAL_API:
        yield
        return

    mock_response = {
        "response": "현재 온도 센서 데이터를 분석했습니다. 모든 센서가 정상 범위 내에 있습니다.",
        "agent_name": "JudgmentAgent",
        "tool_calls": [
            {"tool": "get_sensor_data", "input": {"sensor_type": "temperature"}, "result": {"success": True}},
        ],
        "iterations": 1,
        "routing_info": {"target_agent": "judgment", "intent": "judgment"},
    }
    mock_orchestrator = create_mock_orchestrator(mock_response)

    with patch("app.routers.agents.orchestrator", mock_orchestrator):
        yield


@pytest.fixture(scope="function")
def mock_meta_router_workflow():
    """Mock orchestrator to route to Workflow agent."""
    if USE_REAL_API:
        yield
        return

    mock_response = {
        "response": "온도 알림 워크플로우를 생성했습니다.",
        "agent_name": "WorkflowPlannerAgent",
        "tool_calls": [
            {"tool": "create_workflow", "input": {"name": "Temperature Alert"}, "result": {"success": True}},
        ],
        "iterations": 1,
        "routing_info": {"target_agent": "workflow", "intent": "workflow"},
    }
    mock_orchestrator = create_mock_orchestrator(mock_response)

    with patch("app.routers.agents.orchestrator", mock_orchestrator):
        yield


@pytest.fixture(scope="function")
def mock_meta_router_bi():
    """Mock orchestrator to route to BI agent."""
    if USE_REAL_API:
        yield
        return

    mock_response = {
        "response": "지난 주 생산량 통계입니다: 총 15,230 units",
        "agent_name": "BIPlannerAgent",
        "tool_calls": [
            {"tool": "execute_sql", "input": {"query": "SELECT..."}, "result": {"success": True}},
        ],
        "iterations": 1,
        "routing_info": {"target_agent": "bi", "intent": "bi"},
    }
    mock_orchestrator = create_mock_orchestrator(mock_response)

    with patch("app.routers.agents.orchestrator", mock_orchestrator):
        yield


# ============ E2E Test Fixtures ============

@pytest.fixture
def test_tenant_id():
    """테스트용 Tenant ID."""
    from uuid import uuid4
    return uuid4()


@pytest.fixture
def test_user_id():
    """테스트용 User ID."""
    from uuid import uuid4
    return uuid4()


@pytest_asyncio.fixture
async def e2e_auth_headers() -> dict:
    """
    E2E 테스트용 인증 헤더 생성.

    실제 서버(localhost:8000)에 로그인해서 토큰을 받아옵니다.
    데모 사용자: admin@triflow.ai / admin1234
    """
    import httpx

    tenant_id = "00000000-0000-0000-0000-000000000001"

    # 실제 서버에 로그인
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@triflow.ai",
                "password": "admin1234"
            }
        )

        if login_resp.status_code == 200:
            tokens = login_resp.json().get("tokens", {})
            token = tokens.get("access_token")
        else:
            # 로그인 실패 시 직접 토큰 생성 (테스트용)
            from app.auth.jwt import create_access_token
            token = create_access_token(
                data={
                    "sub": "00000000-0000-0000-0000-000000000101",
                    "tenant_id": tenant_id,
                    "role": "admin",
                    "email": "admin@triflow.ai"
                }
            )

    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id
    }


@pytest.fixture
def e2e_tenant_id():
    """E2E 테스트용 고정 Tenant ID."""
    import uuid
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def e2e_user_id():
    """E2E 테스트용 고정 User ID."""
    import uuid
    return uuid.UUID("00000000-0000-0000-0000-000000000101")
